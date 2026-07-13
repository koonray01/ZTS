from __future__ import annotations

import copy
import inspect
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from ctl_mt5_snapshot import (
    EvidenceStore,
    FixtureSnapshotAdapter,
    MetaTrader5SnapshotAdapter,
    SnapshotAdapter,
    SnapshotUnavailable,
    run_integration_harness,
    validate_snapshot_qc,
)


def test_fixture_snapshot_is_not_live_mt5():
    snapshot = FixtureSnapshotAdapter().capture(symbol="XAUUSD", run_id="RUN-FIXTURE-001", bars=20)
    assert snapshot["source"] == "FIXTURE"
    assert snapshot["source"] != "LIVE_MT5"
    assert snapshot["terminal"]["trade_write_enabled"] is False
    assert {item["timeframe"] for item in snapshot["timeframes"]} >= {"M5", "M15", "H1"}
    assert snapshot["qc"]["decision"] == "PASS"


def test_snapshot_adapter_interface_has_no_trade_methods():
    names = {name for name, _member in inspect.getmembers(SnapshotAdapter)}
    forbidden_fragments = {"send", "open", "close", "modify", "delete", "cancel", "trade"}
    assert not {name for name in names if any(fragment in name.lower() for fragment in forbidden_fragments)}


def test_mt5_unavailable_does_not_fallback_to_fixture():
    fake = SimpleNamespace(initialize=lambda: False, last_error=lambda: ("INIT", "missing terminal"))
    adapter = MetaTrader5SnapshotAdapter(mt5_module=fake)
    with pytest.raises(SnapshotUnavailable):
        adapter.capture(symbol="XAUUSD", run_id="RUN-MT5-UNAVAILABLE", bars=10)


def test_symbol_unavailable_is_explicit():
    fake = SimpleNamespace(
        initialize=lambda: True,
        shutdown=lambda: None,
        symbol_select=lambda _symbol, _enable: False,
        last_error=lambda: ("SYMBOL", "unavailable"),
    )
    adapter = MetaTrader5SnapshotAdapter(mt5_module=fake)
    with pytest.raises(SnapshotUnavailable, match="Symbol is unavailable"):
        adapter.capture(symbol="NOPE", run_id="RUN-SYMBOL-UNAVAILABLE", bars=10)


def test_qc_rejects_open_duplicate_gap_invalid_ohlc_and_stale():
    snapshot = FixtureSnapshotAdapter(capture_time=datetime(2025, 3, 10, 12, 0, 10, tzinfo=timezone.utc)).capture(symbol="XAUUSD", run_id="RUN-QC-001", bars=20)
    broken = copy.deepcopy(snapshot)
    bars = broken["timeframes"][0]["bars"]
    bars[2]["close_time"] = bars[1]["close_time"]
    bars[4]["close_time"] = "2025-03-10T11:59:00Z"
    bars[5]["high"] = bars[5]["low"] - 1
    bars[6]["is_closed"] = False
    result = validate_snapshot_qc(broken, now=datetime(2025, 3, 10, 12, 10, 10, tzinfo=timezone.utc), stale_after_ms=1000)
    assert result["qc"]["decision"] == "QUARANTINE"
    text = " ".join(result["qc"]["errors"])
    assert "duplicate" in text
    assert "missing/gap" in text
    assert "invalid OHLC" in text
    assert "not closed" in text
    assert result["freshness"]["status"] in {"STALE", "BLOCKED"}


def test_evidence_append_only_collision_and_path_traversal(tmp_path):
    store = EvidenceStore(tmp_path)
    snapshot = FixtureSnapshotAdapter().capture(symbol="XAUUSD", run_id="RUN-EVIDENCE-001", bars=20)
    first = store.write_raw_snapshot(snapshot)
    second = store.write_raw_snapshot(snapshot)
    assert first["status"] == "RAW_STORED"
    assert second["status"] == "RAW_STORED"
    changed = copy.deepcopy(snapshot)
    changed["symbol"] = "XAGUSD"
    collision = store.write_raw_snapshot(changed)
    assert collision["status"] == "QUARANTINED"
    unsafe = copy.deepcopy(snapshot)
    unsafe["run_id"] = "../BAD"
    with pytest.raises(ValueError):
        store.write_raw_snapshot(unsafe)


def test_full_pipeline_identity_harness_and_restart_recovery(tmp_path):
    report = run_integration_harness(output_root=tmp_path, iterations=3)
    assert report["final_decision"] == "CONDITIONAL_GO_PENDING_REAL_MT5"
    assert report["snapshots_processed"] == 3
    assert report["unique_market_state_hashes"] >= 1
    assert report["worker_result_count"] == report["jobs_created"]
    assert report["worker_invocations"] == report["worker_result_count"]
    assert report["worker_invocations_per_unique_state"] <= report["snapshots_processed"]
    assert set(report["candidate_suppression_breakdown"]) == {
        "NO_VALID_LOCATION",
        "NO_ACTIVE_ZONE",
        "NO_OPPORTUNITY",
        "SCENARIO_NOT_READY",
        "TRIGGER_PENDING",
        "RR_BELOW_MINIMUM",
        "CONFLICT_BLOCK",
        "SHOCK_BLOCK",
        "SNAPSHOT_QC_BLOCK",
        "STALE_DATA_BLOCK",
        "REQUIRED_INPUT_UNKNOWN",
        "LIMIT_NOT_ELIGIBLE",
        "ENTRY_EXPIRED",
        "STRUCTURE_NOT_CONFIRMED",
        "SETUP_FAMILY_NOT_READY",
        "POLICY_BLOCK",
        "OTHER_EXPLICIT_REASON",
    }
    assert report["stage_timeouts"] == 0
    assert report["manual_termination"] is False
    assert report["completed_snapshots"] == 3
    assert report["opportunity_count"] >= 3
    assert report["candidate_count"] >= 0
    assert report["paused_position_monitoring_active"] is True
    assert report["auto_execution_enabled"] is False
    assert report["trade_write_enabled"] is False
    assert report["order_actions"] == 0
    assert report["integrity"]["errors"] == []


def test_forward_shadow_cli_reports_pending_when_real_mt5_unavailable(root, monkeypatch, tmp_path):
    script = root / "tools" / "run_forward_shadow.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--output", str(tmp_path), "--snapshots", "1"],
        capture_output=True,
        text=True,
    )
    if completed.returncode == 3:
        payload = json.loads(completed.stderr)
        assert payload["status"] == "REAL_MT5_VALIDATION_PENDING"
        assert payload["fallback_used"] is False
    else:
        assert completed.returncode in {0, 2}


def test_forward_shadow_acceptance_classification(root):
    sys.path.insert(0, str(root / "tools"))
    import run_forward_shadow

    base = {
        "source": "LIVE_MT5",
        "completed_requested_snapshots": True,
        "snapshots_processed": 20,
        "order_actions": 0,
        "stopped_reason": None,
    }
    assert run_forward_shadow.classify_acceptance(base) == ("ACCEPTED_REAL_FORWARD_SHADOW_MINIMUM", True)

    smoke = dict(base, snapshots_processed=3)
    assert run_forward_shadow.classify_acceptance(smoke) == ("REAL_MT5_SMOKE_ONLY", False)

    canary = dict(base, requested_snapshots=10, snapshots_processed=10)
    assert run_forward_shadow.classify_acceptance(canary) == ("TIMED_CANARY_PASS", True)

    stalled = dict(base, stopped_reason="SNAPSHOT_STAGE_TIMEOUT:RUN:301.0s")
    assert run_forward_shadow.classify_acceptance(stalled) == ("TIMED_SHADOW_INTERRUPTED_STALL", False)

    fixture = dict(base, source="FIXTURE")
    assert run_forward_shadow.classify_acceptance(fixture) == ("REAL_MT5_VALIDATION_PENDING", False)

    incomplete = dict(base, completed_requested_snapshots=False)
    assert run_forward_shadow.classify_acceptance(incomplete) == ("INCOMPLETE_REQUESTED_SNAPSHOTS", False)
