from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from ctl_analysis_registry.catchup import registry_status, run_catchup
from ctl_analysis_registry.events import build_v2_event
from ctl_analysis_registry.index import rebuild_index
from ctl_analysis_registry.lease import RegistryWriterLease
from ctl_analysis_registry.paths import resolve_registry_paths
from ctl_analysis_registry.ledger import AppendOnlyLedger
from ctl_analysis_registry.scheduler import schedule_jobs


NOW = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)


def _safety():
    return {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0}


def _decision(index=1):
    return {
        "decision_id": f"DECISION_{index}", "analysis_id": "ANALYSIS_1", "view_id": "VIEW_1",
        "system": "ZENITH", "decision_type": "DIRECTIONAL", "decision_subtype": "UNCONDITIONAL_DIRECTIONAL",
        "prediction_family_id": f"FAMILY_{index}", "semantic_opportunity_id": None, "variant_id": None,
        "symbol": "XAUUSD", "direction": "BULLISH", "action": "WATCH", "role": "PRIMARY",
        "decision_time": NOW.isoformat(), "evaluation_start": NOW.isoformat(), "horizons": ["PT15M"],
        "labeling_policy_version": "DIRECTIONAL_TERMINAL_ATR_V1", "engine_version": "TEST",
        "timeframe_scope": ["M5"],
        "rules": {"success": "UP", "failure": "DOWN", "invalidation": "BAD_SOURCE", "expiry": "HORIZON_END"},
        "market_context": {"regime": "RANGE", "volatility": "NORMAL"},
        "source_bindings": {"snapshot_id": "SNAP_1", "manifest_hash": "a" * 64, "evidence_hashes": ["b" * 64]},
        "quality": {"source_qc": "PASS", "freshness": "FRESH", "integrity_tier": "VERIFIED", "scorable_status": "SCORABLE"},
        "reference_price": {"method": "DECISION_TIME_MID", "value": 100.0},
        "atr": {"timeframe": "M5", "period": 14, "method": "WILDER", "value": 1.0},
        "source_class": "LIVE_MT5", "safety": _safety(),
    }


def _fields(event_id, event_type, payload):
    return {
        "event_id": event_id, "event_type": event_type, "event_time": NOW.isoformat(),
        "decision_time": NOW.isoformat(), "source_class": "LIVE_MT5",
        "integrity_tier": "VERIFIED", "producer": "catchup-test", "payload": payload,
    }


def _registry(tmp_path: Path, count=1):
    ledger_path = tmp_path / "events.jsonl"
    sqlite_path = tmp_path / "index.sqlite"
    evidence_root = tmp_path / "evidence"
    ledger = AppendOnlyLedger(ledger_path)
    previous = None
    for index in range(1, count + 1):
        decision = _decision(index)
        frozen = build_v2_event(_fields(f"E_D_{index}", "DECISION_FROZEN", decision), previous_hash=previous)
        ledger.append_fsynced(frozen)
        previous = frozen["event_hash"]
        job = schedule_jobs(decision)[0]
        job.update({
            "system": "ZENITH", "decision_type": "DIRECTIONAL", "symbol": "XAUUSD", "timeframe": "M5",
            "source_binding": {"source": "LIVE_MT5", "server": "TEST", "symbol": "XAUUSD", "digits": 2, "point": 0.01, "broker_utc_offset_minutes": 0},
            "max_terminal_lag_seconds": 300,
        })
        event = build_v2_event(_fields(f"E_J_{index}", "EVALUATION_JOB_SCHEDULED", job), previous_hash=previous)
        ledger.append_fsynced(event)
        previous = event["event_hash"]
    rebuild_index(ledger_path, sqlite_path)
    return {"ledger_path": ledger_path, "sqlite_path": sqlite_path, "evidence_root": evidence_root}


class _Adapter:
    def closed_bars_between(self, symbol, timeframe, start, end):
        return [
            {"bar_id": "B1", "timeframe": "M5", "open_time": "2026-07-22T09:05:00Z", "close_time": "2026-07-22T09:10:00Z", "open": 100.0, "high": 100.2, "low": 99.9, "close": 100.1, "spread_points": 10, "is_closed": True},
            {"bar_id": "B2", "timeframe": "M5", "open_time": "2026-07-22T09:10:00Z", "close_time": "2026-07-22T09:15:00Z", "open": 100.1, "high": 100.4, "low": 100.0, "close": 100.3, "spread_points": 10, "is_closed": True},
        ]

    def ticks_between(self, symbol, start, end):
        return []


def test_overdue_jobs_resolve_after_restart_without_duplicates(tmp_path: Path) -> None:
    paths = _registry(tmp_path)
    first = run_catchup(**paths, adapter=_Adapter(), now=NOW + timedelta(minutes=20), max_jobs=10)
    second = run_catchup(**paths, adapter=_Adapter(), now=NOW + timedelta(minutes=20), max_jobs=10)

    assert first["resolved"] == 1
    assert second["resolved"] == 0
    assert second["duplicate_outcomes"] == 0
    assert len([event for event in AppendOnlyLedger(paths["ledger_path"]).read_all() if event["event_type"] == "MODEL_OUTCOME_RECORDED"]) == 1


def test_max_jobs_returns_partial_with_remaining_count(tmp_path: Path) -> None:
    paths = _registry(tmp_path, count=3)

    result = run_catchup(**paths, adapter=_Adapter(), now=NOW + timedelta(minutes=20), max_jobs=1)

    assert result["status"] == "PARTIAL"
    assert result["processed"] == 1
    assert result["remaining"] == 2


def test_catchup_defers_when_writer_lease_is_held(tmp_path: Path) -> None:
    paths = _registry(tmp_path)
    registry_paths = resolve_registry_paths(paths["ledger_path"].parent)
    lease = RegistryWriterLease.acquire(registry_paths.lease, "other", 30, now=NOW + timedelta(minutes=20))
    try:
        result = run_catchup(**paths, adapter=_Adapter(), now=NOW + timedelta(minutes=20), max_jobs=1)
    finally:
        lease.release()
    assert result["status"] == "DEFERRED"
    assert result["processed"] == 0


def test_registry_status_reports_due_and_safety(tmp_path: Path) -> None:
    paths = _registry(tmp_path)
    status = registry_status(paths["sqlite_path"], NOW + timedelta(minutes=20))
    assert status["due"] == 1
    assert status["safety"] == _safety()
