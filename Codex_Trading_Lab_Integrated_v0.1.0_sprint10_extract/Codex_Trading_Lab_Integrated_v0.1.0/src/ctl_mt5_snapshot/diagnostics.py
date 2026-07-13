from __future__ import annotations

import queue
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterator

from .utils import atomic_write_json, iso_z


STALL_CATEGORIES = {
    "MT5_API_BLOCK",
    "TERMINAL_UNRESPONSIVE",
    "SYMBOL_SYNC_DELAY",
    "DATA_COPY_TIMEOUT",
    "FILE_WRITE_STALL",
    "LOCK_CONTENTION",
    "PIPELINE_STAGE_STALL",
    "WORKER_STALL",
    "SYSTEM_SLEEP_OR_SUSPEND",
    "CLOCK_JUMP",
    "UNKNOWN_STALL",
}


class StageTimeout(RuntimeError):
    def __init__(self, *, stage: str, elapsed_seconds: float, category: str):
        super().__init__(f"{stage} timed out after {elapsed_seconds:.3f}s")
        if category not in STALL_CATEGORIES:
            category = "UNKNOWN_STALL"
        self.stage = stage
        self.elapsed_seconds = elapsed_seconds
        self.category = category


def run_with_timeout(func: Callable[[], Any], *, timeout_seconds: float, stage: str, category: str) -> Any:
    results: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def target() -> None:
        try:
            results.put(("ok", func()))
        except BaseException as exc:  # noqa: BLE001 - preserve adapter exceptions across thread boundary.
            results.put(("error", exc))

    started = perf_counter()
    thread = threading.Thread(target=target, name=f"ctl-{stage}-timeout", daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    elapsed = perf_counter() - started
    if thread.is_alive():
        raise StageTimeout(stage=stage, elapsed_seconds=elapsed, category=category)
    status, payload = results.get_nowait()
    if status == "error":
        raise payload
    return payload


class IterationDiagnostics:
    def __init__(self, *, output_root: str | Path, iteration_index: int, run_id: str):
        self.output_root = Path(output_root)
        self.iteration_index = iteration_index
        self.run_id = run_id
        self.path = self.output_root / "diagnostics" / f"iteration_{iteration_index:03d}.json"
        now = iso_z(datetime.now(timezone.utc))
        self.record: dict[str, Any] = {
            "iteration_index": iteration_index,
            "run_id": run_id,
            "snapshot_id": None,
            "iteration_started_at": now,
            "iteration_completed_at": None,
            "last_heartbeat_at": now,
            "current_stage": "START",
            "current_stage_started_at": now,
            "timeout_triggered": False,
            "timeout_category": None,
            "timeout_elapsed_seconds": None,
            "recoverable": True,
            "terminal_connected": None,
            "symbol_synchronized": None,
            "last_tick_age_seconds": None,
            "reconnect_attempted": False,
            "stage_seconds": {},
            "snapshot_capture_seconds": None,
            "snapshot_qc_seconds": None,
            "evidence_write_seconds": None,
            "basic_eyes_seconds": None,
            "advanced_eyes_seconds": None,
            "fusion_seconds": None,
            "scenario_seconds": None,
            "entry_seconds": None,
            "watcher_seconds": None,
            "worker_seconds": None,
            "knowledge_output_seconds": None,
            "total_iteration_seconds": None,
        }
        self._iteration_started = perf_counter()
        self.persist()

    def persist(self) -> None:
        atomic_write_json(self.path, self.record)

    def heartbeat(self, stage: str) -> None:
        now = iso_z(datetime.now(timezone.utc))
        self.record["last_heartbeat_at"] = now
        if self.record.get("current_stage") != stage:
            self.record["current_stage"] = stage
            self.record["current_stage_started_at"] = now
        self.persist()

    @contextmanager
    def stage(self, stage: str, metric: str | None = None) -> Iterator[None]:
        self.heartbeat(stage)
        started = perf_counter()
        try:
            yield
        finally:
            elapsed = perf_counter() - started
            key = metric or f"{stage.lower()}_seconds"
            self.record["stage_seconds"][stage] = round(elapsed, 6)
            if key in self.record:
                current = self.record[key]
                self.record[key] = round((current or 0) + elapsed, 6)
            self.persist()

    def attach_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.record["snapshot_id"] = snapshot.get("snapshot_id")
        terminal = snapshot.get("terminal", {})
        self.record["terminal_connected"] = terminal.get("connected")
        self.record["symbol_synchronized"] = snapshot.get("qc", {}).get("decision") == "PASS"
        freshness = snapshot.get("freshness", {})
        age_ms = freshness.get("age_ms")
        self.record["last_tick_age_seconds"] = None if age_ms is None else round(float(age_ms) / 1000, 3)
        self.persist()

    def mark_timeout(self, timeout: StageTimeout) -> None:
        self.record["timeout_triggered"] = True
        self.record["timeout_category"] = timeout.category
        self.record["timeout_elapsed_seconds"] = round(timeout.elapsed_seconds, 6)
        self.record["recoverable"] = False
        self.record["current_stage"] = timeout.stage
        self.persist()

    def complete(self) -> None:
        self.record["iteration_completed_at"] = iso_z(datetime.now(timezone.utc))
        self.record["total_iteration_seconds"] = round(perf_counter() - self._iteration_started, 6)
        self.record["current_stage"] = "COMPLETE"
        self.persist()
