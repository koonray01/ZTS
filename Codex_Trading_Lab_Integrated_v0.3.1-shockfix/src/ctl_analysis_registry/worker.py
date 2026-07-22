"""Optional finite foreground worker for Analysis Registry catch-up."""

from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .catchup import SAFETY, run_catchup


def _atomic_control(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_worker(config: dict[str, Any], stop_file: str | Path) -> dict[str, Any]:
    cycles = int(config.get("cycles", 1))
    if cycles < 0:
        raise ValueError("cycles cannot be negative")
    stop_file = Path(stop_file)
    control_path = Path(config["control_path"])
    processed = resolved = 0
    last_status = "NOT_RUN"
    completed_cycles = 0
    for cycle in range(cycles):
        if stop_file.exists():
            stop_file.unlink()
            last_status = "STOPPED"
            break
        now_value = config.get("now")
        now = now_value() if callable(now_value) else now_value or datetime.now(timezone.utc)
        result = run_catchup(
            ledger_path=config["ledger_path"], sqlite_path=config["sqlite_path"],
            evidence_root=config["evidence_root"], adapter=config["adapter"],
            now=now, max_jobs=int(config.get("max_jobs", 25)),
            paths=config.get("paths"),
        )
        completed_cycles += 1
        processed += int(result.get("processed", 0))
        resolved += int(result.get("resolved", 0))
        last_status = str(result["status"])
        _atomic_control(
            control_path,
            {"status": last_status, "cycle": cycle + 1, "heartbeat_at": now.isoformat(), "processed": processed, "resolved": resolved, "safety": deepcopy(SAFETY)},
        )
        interval = float(config.get("interval_seconds", 0))
        if interval > 0 and cycle + 1 < cycles:
            time.sleep(interval)
    result = {
        "status": last_status, "cycles": completed_cycles, "processed": processed,
        "resolved": resolved, "safety": deepcopy(SAFETY),
    }
    _atomic_control(control_path, result)
    return result
