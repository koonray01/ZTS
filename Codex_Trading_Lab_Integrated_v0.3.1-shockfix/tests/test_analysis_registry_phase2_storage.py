from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ctl_analysis_registry.events import build_v2_event
from ctl_analysis_registry.index import rebuild_index
from ctl_analysis_registry.lease import LeaseBusyError, RegistryWriterLease
from ctl_analysis_registry.ledger import AppendOnlyLedger, LedgerError


NOW = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)


def _safety() -> dict:
    return {
        "trade_write_enabled": False,
        "auto_execution_enabled": False,
        "order_actions": 0,
        "permission_leakage": 0,
    }


def _decision() -> dict:
    return {
        "decision_id": "DECISION_1", "analysis_id": "ANALYSIS_1", "view_id": "VIEW_1",
        "system": "ZENITH", "decision_type": "DIRECTIONAL",
        "decision_subtype": "UNCONDITIONAL_DIRECTIONAL",
        "prediction_family_id": "PRED_ZENITH_XAU", "semantic_opportunity_id": None,
        "variant_id": None, "symbol": "XAUUSD", "direction": "BULLISH",
        "action": "WATCH", "role": "PRIMARY", "decision_time": NOW.isoformat(),
        "horizons": ["PT15M"], "labeling_policy_version": "DIRECTIONAL_TERMINAL_ATR_V1",
        "engine_version": "ZENITH_TEST", "timeframe_scope": ["M15"],
        "rules": {"success": "UP", "failure": "DOWN", "invalidation": "BAD_SOURCE", "expiry": "HORIZON_END"},
        "market_context": {"regime": "RANGE", "volatility": "NORMAL"},
        "source_bindings": {"snapshot_id": "SNAP_1", "manifest_hash": "a" * 64, "evidence_hashes": ["b" * 64]},
        "quality": {"source_qc": "PASS", "freshness": "FRESH", "integrity_tier": "VERIFIED", "scorable_status": "SCORABLE"},
        "safety": _safety(),
        "reference_price": {"method": "DECISION_TIME_MID", "value": 4018.5},
        "atr": {"timeframe": "M15", "period": 14, "method": "WILDER", "value": 4.0},
    }


def _job() -> dict:
    return {
        "job_id": "JOB_1", "decision_id": "DECISION_1", "horizon": "PT15M",
        "labeling_policy_version": "DIRECTIONAL_TERMINAL_ATR_V1", "state": "PENDING",
        "due_at": (NOW + timedelta(minutes=15)).isoformat(), "safety": _safety(),
    }


def _event(event_id: str, event_type: str, payload: dict, previous_hash: str | None) -> dict:
    return build_v2_event(
        {
            "event_id": event_id, "event_type": event_type, "event_time": NOW.isoformat(),
            "decision_time": NOW.isoformat(), "source_class": "LIVE_MT5",
            "integrity_tier": "VERIFIED", "producer": "storage-test", "payload": payload,
        },
        previous_hash=previous_hash,
    )


def _ledger_with_phase2_events(tmp_path: Path) -> tuple[Path, Path, list[dict]]:
    ledger_path = tmp_path / "events.jsonl"
    sqlite_path = tmp_path / "index.sqlite"
    ledger = AppendOnlyLedger(ledger_path)
    frozen = _event("EVENT_DECISION", "DECISION_FROZEN", _decision(), None)
    scheduled = _event("EVENT_JOB", "EVALUATION_JOB_SCHEDULED", _job(), frozen["event_hash"])
    ledger.append_fsynced(frozen)
    ledger.append_fsynced(scheduled)
    return ledger_path, sqlite_path, [frozen, scheduled]


def test_second_live_writer_cannot_acquire_registry_lease(tmp_path: Path) -> None:
    lease_path = tmp_path / "registry.lease.json"
    first = RegistryWriterLease.acquire(lease_path, "owner-a", ttl_seconds=30, now=NOW)
    with pytest.raises(LeaseBusyError):
        RegistryWriterLease.acquire(lease_path, "owner-b", ttl_seconds=30, now=NOW)
    first.release()


def test_stale_writer_lease_is_recovered_with_operation_record(tmp_path: Path) -> None:
    lease_path = tmp_path / "registry.lease.json"
    operation_log = tmp_path / "operations.jsonl"
    RegistryWriterLease.acquire(lease_path, "owner-a", ttl_seconds=1, now=NOW)

    recovered = RegistryWriterLease.acquire(
        lease_path, "owner-b", ttl_seconds=30, now=NOW + timedelta(seconds=2),
        operation_log=operation_log,
    )

    assert recovered.owner_id == "owner-b"
    record = json.loads(operation_log.read_text(encoding="utf-8").splitlines()[0])
    assert record["event"] == "STALE_REGISTRY_LEASE_RECOVERED"
    assert record["previous_owner_id"] == "owner-a"
    recovered.release()


def test_partial_ledger_tail_is_rejected_before_fsynced_append(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"event_id":"PARTIAL"')
    original = path.read_bytes()

    with pytest.raises(LedgerError, match="partial|invalid JSON"):
        AppendOnlyLedger(path).append_fsynced(_event("EVENT_1", "DECISION_FROZEN", _decision(), None))

    assert path.read_bytes() == original


def test_rebuilt_projection_binds_to_ledger_head(tmp_path: Path) -> None:
    ledger, sqlite, events = _ledger_with_phase2_events(tmp_path)

    counts = rebuild_index(ledger, sqlite)

    with sqlite3.connect(sqlite) as connection:
        metadata = connection.execute(
            "SELECT projection_schema_version, ledger_head_hash FROM projection_metadata"
        ).fetchone()
    assert metadata == ("ANALYSIS_REGISTRY_PROJECTION_V0_2", events[-1]["event_hash"])
    assert counts["frozen_decisions"] == 1
    assert counts["evaluation_jobs"] == 1
