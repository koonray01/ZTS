"""Bounded, lease-protected model outcome catch-up orchestration."""

from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .abstention import label_abstention
from .database import open_readonly_sqlite
from .directional import label_directional
from .events import build_v2_event
from .followup import collect_followup
from .identity import stable_id
from .index import rebuild_index
from .coordination import acquire_registry_writer
from .lease import LeaseBusyError
from .ledger import AppendOnlyLedger
from .paths import RegistryPaths, resolve_registry_paths, validate_mutation_paths
from .scenario import label_scenario
from .scheduler import due_jobs
from .setup import label_setup


SAFETY = {
    "trade_write_enabled": False,
    "auto_execution_enabled": False,
    "order_actions": 0,
    "permission_leakage": 0,
}


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_typed(
    ledger: AppendOnlyLedger,
    event_type: str,
    payload: dict[str, Any],
    *,
    now: datetime,
    decision_time: str,
    source_class: str,
    integrity_tier: str,
) -> str:
    identity = payload.get("evidence_id") or payload.get("outcome_id") or stable_id(event_type, payload)
    event_id = stable_id("EVENT", event_type, identity)
    events = ledger.read_all()
    existing = next((event for event in events if event.get("event_id") == event_id), None)
    if existing is not None:
        return ledger.append_fsynced(existing)
    event = build_v2_event(
        {
            "event_id": event_id, "event_type": event_type, "event_time": _iso(now),
            "decision_time": decision_time, "source_class": source_class,
            "integrity_tier": integrity_tier, "producer": "ctl_analysis_registry.catchup",
            "payload": payload,
        },
        previous_hash=events[-1]["event_hash"] if events else None,
    )
    return ledger.append_fsynced(event)


def _decision(connection: sqlite3.Connection, decision_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT payload_json FROM frozen_decisions WHERE decision_id=?", (decision_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"frozen decision not found: {decision_id}")
    return json.loads(row[0])


def _enrich_job(job: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    enriched = deepcopy(job)
    enriched.setdefault("system", decision["system"])
    enriched.setdefault("decision_type", decision["decision_type"])
    enriched.setdefault("symbol", decision["symbol"])
    enriched.setdefault("timeframe", next((tf for tf in decision.get("timeframe_scope", []) if tf != "UNKNOWN"), "M5"))
    binding = enriched.get("source_binding")
    if not isinstance(binding, dict):
        frozen = decision.get("source_bindings", {})
        binding = {
            "source": decision.get("source_class", "LIVE_MT5"), "server": frozen.get("server"),
            "symbol": decision["symbol"], "digits": frozen.get("digits"), "point": frozen.get("point"),
            "broker_utc_offset_minutes": frozen.get("broker_utc_offset_minutes"),
            "overlap_fingerprint": frozen.get("overlap_fingerprint"),
        }
        enriched["source_binding"] = binding
    enriched.setdefault("max_terminal_lag_seconds", 300)
    enriched["safety"] = deepcopy(SAFETY)
    return enriched


def _label(
    decision: dict[str, Any],
    job: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    decision_type = decision["decision_type"]
    if decision_type == "DIRECTIONAL":
        outcome = label_directional(decision, job, evidence)
    elif decision_type == "SCENARIO":
        outcome = label_scenario(decision, job, evidence)
    elif decision_type == "SETUP":
        outcome = label_setup(decision, evidence)
    elif decision_type == "ABSTENTION":
        outcome = label_abstention(decision, evidence.get("control_outcome"))
    else:
        raise ValueError(f"unsupported decision type: {decision_type}")
    outcome.setdefault("horizon", job["horizon"])
    outcome.setdefault("evidence_refs", evidence.get("evidence_refs", []))
    outcome.setdefault("safety", deepcopy(SAFETY))
    outcome["job_id"] = job["job_id"]
    outcome["semantic_opportunity_id"] = decision.get("semantic_opportunity_id")
    outcome["variant_id"] = decision.get("variant_id")
    outcome["integrity_tier"] = decision.get("quality", {}).get("integrity_tier", "PARTIAL")
    return outcome


def run_catchup(
    ledger_path: str | Path,
    sqlite_path: str | Path,
    evidence_root: str | Path,
    adapter: Any,
    now: datetime,
    max_jobs: int,
    paths: RegistryPaths | None = None,
) -> dict[str, Any]:
    ledger_path, sqlite_path = Path(ledger_path), Path(sqlite_path)
    if max_jobs < 0:
        raise ValueError("max_jobs cannot be negative")
    paths = paths or resolve_registry_paths(ledger_path.parent)
    validate_mutation_paths(paths, ledger_path=ledger_path, sqlite_path=sqlite_path, evidence_root=evidence_root)
    try:
        lease = acquire_registry_writer(paths, stable_id("CATCHUP_OWNER", _iso(now)), now)
    except LeaseBusyError:
        return {"status": "DEFERRED", "processed": 0, "resolved": 0, "remaining": 0, "duplicate_outcomes": 0, "safety": deepcopy(SAFETY)}
    processed = resolved = duplicate_outcomes = failures = 0
    try:
        rebuild_index(ledger_path, sqlite_path)
        connection = sqlite3.connect(sqlite_path)
        try:
            all_due = due_jobs(connection, now, 1_000_000)
            selected = all_due[:max_jobs]
            decisions = {job["decision_id"]: _decision(connection, job["decision_id"]) for job in selected}
        finally:
            connection.close()
        ledger = AppendOnlyLedger(ledger_path)
        for raw_job in selected:
            decision = decisions[raw_job["decision_id"]]
            job = _enrich_job(raw_job, decision)
            try:
                evidence = collect_followup(job, adapter, evidence_root)
                _append_typed(
                    ledger, "FOLLOWUP_EVIDENCE_RECORDED", evidence, now=now,
                    decision_time=decision["decision_time"], source_class=decision.get("source_class", "LIVE_MT5"),
                    integrity_tier=decision.get("quality", {}).get("integrity_tier", "PARTIAL"),
                )
                outcome = _label(decision, job, evidence)
                existing_outcome = any(
                    event.get("event_type") == "MODEL_OUTCOME_RECORDED"
                    and event.get("payload", {}).get("outcome_id") == outcome["outcome_id"]
                    for event in ledger.read_all()
                )
                if existing_outcome:
                    duplicate_outcomes += 1
                else:
                    _append_typed(
                        ledger, "MODEL_OUTCOME_RECORDED", outcome, now=now,
                        decision_time=decision["decision_time"], source_class=decision.get("source_class", "LIVE_MT5"),
                        integrity_tier=decision.get("quality", {}).get("integrity_tier", "PARTIAL"),
                    )
                    resolved += 1
                processed += 1
            except Exception:
                failures += 1
        rebuild_index(ledger_path, sqlite_path)
        remaining = max(0, len(all_due) - processed)
        status = "PARTIAL" if remaining or failures else "COMPLETE"
        return {
            "status": status, "processed": processed, "resolved": resolved,
            "remaining": remaining, "failures": failures,
            "duplicate_outcomes": duplicate_outcomes, "safety": deepcopy(SAFETY),
        }
    finally:
        lease.release()


def registry_status(sqlite_path: str | Path, now: datetime) -> dict[str, Any]:
    connection = open_readonly_sqlite(sqlite_path)
    try:
        states = dict(connection.execute("SELECT state, COUNT(*) FROM evaluation_jobs GROUP BY state").fetchall())
        due = int(connection.execute(
            "SELECT COUNT(*) FROM evaluation_jobs WHERE state IN ('PENDING','DUE','RETRY_PENDING') AND due_at <= ?",
            (_iso(now),),
        ).fetchone()[0])
        metadata = connection.execute(
            "SELECT projection_schema_version, ledger_head_hash, event_count FROM projection_metadata"
        ).fetchone()
    finally:
        connection.close()
    return {
        "status": "PASS", "states": states, "due": due,
        "projection_schema_version": metadata[0], "ledger_head_hash": metadata[1], "event_count": metadata[2],
        "safety": deepcopy(SAFETY),
    }
