"""Freeze-first integration boundary for normal read-only analysis routes."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .catchup import SAFETY, run_catchup
from .chat_model import freeze_chat_model_view
from .events import build_v2_event
from .identity import stable_id
from .index import rebuild_index
from .lease import RegistryWriterLease
from .ledger import AppendOnlyLedger
from .recorder import freeze_zenith_decisions, record_frozen_decisions
from .scheduler import schedule_jobs


def register_current_analysis(
    *,
    decision_state: dict[str, Any],
    snapshot: dict[str, Any],
    analysis_id: str,
    ledger_path: str | Path,
    sqlite_path: str | Path,
    now: datetime,
    chat_envelope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ledger_path, sqlite_path = Path(ledger_path), Path(sqlite_path)
    lease = RegistryWriterLease.acquire(
        ledger_path.with_suffix(".lease.json"), stable_id("ANALYSIS_REGISTRY_WRITER", analysis_id, now.isoformat()),
        60, now=now, operation_log=ledger_path.with_suffix(".operations.jsonl"),
    )
    try:
        decisions = freeze_zenith_decisions(decision_state, snapshot, analysis_id)
        if chat_envelope is not None:
            decisions.extend(freeze_chat_model_view(chat_envelope, snapshot))
        decision_ids = record_frozen_decisions(AppendOnlyLedger(ledger_path), decisions)
        ledger = AppendOnlyLedger(ledger_path)
        scheduled = 0
        for decision in decisions:
            if decision.get("quality", {}).get("scorable_status") != "SCORABLE":
                continue
            for job in schedule_jobs(decision):
                job.update(
                    {
                        "system": decision["system"], "decision_type": decision["decision_type"],
                        "symbol": decision["symbol"],
                        "timeframe": next((tf for tf in decision.get("timeframe_scope", []) if tf != "UNKNOWN"), "M5"),
                        "source_binding": {
                            "source": decision.get("source_class", "LIVE_MT5"),
                            "server": decision.get("source_bindings", {}).get("server"),
                            "symbol": decision["symbol"],
                            "digits": decision.get("source_bindings", {}).get("digits"),
                            "point": decision.get("source_bindings", {}).get("point"),
                            "broker_utc_offset_minutes": decision.get("source_bindings", {}).get("broker_utc_offset_minutes"),
                            "overlap_fingerprint": decision.get("source_bindings", {}).get("overlap_fingerprint"),
                        },
                        "max_terminal_lag_seconds": 300,
                    }
                )
                event_id = stable_id("EVENT", "EVALUATION_JOB_SCHEDULED", job["job_id"])
                events = ledger.read_all()
                if any(event.get("event_id") == event_id for event in events):
                    continue
                event = build_v2_event(
                    {
                        "event_id": event_id, "event_type": "EVALUATION_JOB_SCHEDULED",
                        "event_time": now.isoformat(), "decision_time": decision["decision_time"],
                        "source_class": decision.get("source_class", "LIVE_MT5"),
                        "integrity_tier": decision["quality"]["integrity_tier"],
                        "producer": "ctl_analysis_registry.integration", "payload": job,
                    },
                    previous_hash=events[-1]["event_hash"] if events else None,
                )
                ledger.append_fsynced(event)
                scheduled += 1
        rebuild_index(ledger_path, sqlite_path)
        return {"decision_ids": decision_ids, "scheduled": scheduled}
    finally:
        lease.release()


def register_analysis_and_catchup(
    *,
    decision_state: dict[str, Any],
    snapshot: dict[str, Any],
    analysis_id: str,
    ledger_path: str | Path,
    sqlite_path: str | Path,
    evidence_root: str | Path,
    adapter: Any,
    now: datetime,
    max_jobs: int,
    chat_envelope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        recording = register_current_analysis(
            decision_state=decision_state, snapshot=snapshot, analysis_id=analysis_id,
            ledger_path=ledger_path, sqlite_path=sqlite_path, now=now,
            chat_envelope=chat_envelope,
        )
    except Exception as exc:
        return {
            "registry_recording_status": "ANALYSIS_NOT_REGISTERED",
            "registry_error": f"{type(exc).__name__}: {exc}",
            "catchup_status": "BLOCKED", "catchup_processed": 0, "catchup_remaining": 0,
            **deepcopy(SAFETY),
        }
    catchup = run_catchup(
        ledger_path=ledger_path, sqlite_path=sqlite_path, evidence_root=evidence_root,
        adapter=adapter, now=now, max_jobs=max_jobs,
    )
    return {
        "registry_recording_status": "RECORDED", "registered_decision_ids": recording["decision_ids"],
        "scheduled_jobs": recording["scheduled"], "catchup_status": catchup["status"],
        "catchup_processed": catchup.get("processed", 0), "catchup_remaining": catchup.get("remaining", 0),
        **deepcopy(SAFETY),
    }
