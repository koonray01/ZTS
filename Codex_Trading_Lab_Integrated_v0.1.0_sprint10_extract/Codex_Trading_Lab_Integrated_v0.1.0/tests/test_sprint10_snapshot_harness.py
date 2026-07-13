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
from ctl_decision_core.watcher import diff_decision_state


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


def test_mt5_adapter_normalizes_broker_time_offset():
    class Row(dict):
        dtype = SimpleNamespace(names=("time", "open", "high", "low", "close", "tick_volume", "spread"))

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    broker_now = now + timedelta(hours=3)

    def rows_for(tf_minutes: int):
        base_dt = broker_now - timedelta(minutes=tf_minutes * 3)
        base = int(base_dt.timestamp())
        return [
            Row(time=base + tf_minutes * 60 * index, open=100 + index, high=101 + index, low=99 + index, close=100.5 + index, tick_volume=10, spread=20)
            for index in range(2)
        ]

    fake = SimpleNamespace(
        TIMEFRAME_M5=5,
        TIMEFRAME_M15=15,
        TIMEFRAME_H1=60,
        TIMEFRAME_H4=240,
        initialize=lambda: True,
        shutdown=lambda: None,
        symbol_select=lambda _symbol, _enable: True,
        terminal_info=lambda: SimpleNamespace(name="TEST", connected=True, build=1),
        account_info=lambda: SimpleNamespace(login=12345678, server="TEST", currency="USD", balance=1.0, equity=1.0, margin_free=1.0),
        symbol_info_tick=lambda _symbol: SimpleNamespace(time=int(broker_now.timestamp())),
        positions_get=lambda symbol: [],
        copy_rates_from_pos=lambda _symbol, timeframe, _start, _bars: rows_for({5: 5, 15: 15, 60: 60, 240: 240}[timeframe]),
        last_error=lambda: None,
    )
    adapter = MetaTrader5SnapshotAdapter(mt5_module=fake)
    snapshot = adapter.capture(symbol="XAUUSD", run_id="RUN-OFFSET", bars=2)
    assert snapshot["broker_utc_offset_minutes"] > 0
    latest_close = snapshot["timeframes"][0]["bars"][-1]["close_time"]
    assert latest_close <= snapshot["capture_time"]


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


def test_qc_allows_market_closure_gap_as_warning():
    snapshot = FixtureSnapshotAdapter(capture_time=datetime(2026, 7, 13, 12, 0, 10, tzinfo=timezone.utc)).capture(symbol="XAUUSD", run_id="RUN-QC-WEEKEND", bars=20)
    frame = next(item for item in snapshot["timeframes"] if item["timeframe"] == "H1")
    frame["bars"][-2]["close_time"] = "2026-07-10T21:00:00Z"
    frame["bars"][-1]["open_time"] = "2026-07-13T00:00:00Z"
    frame["bars"][-1]["close_time"] = "2026-07-13T01:00:00Z"
    frame["last_closed_bar_time"] = frame["bars"][-1]["close_time"]
    result = validate_snapshot_qc(snapshot, now=datetime(2026, 7, 13, 12, 0, 10, tzinfo=timezone.utc), stale_after_ms=10_000_000)
    assert "market-closure gap" in " ".join(result["qc"]["warnings"])


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


def test_full_pipeline_identity_harness_and_runtime_reinitialization_recovery(tmp_path):
    report = run_integration_harness(output_root=tmp_path, iterations=3, runtime_reinitialize_after_snapshot=1)
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
    assert report["primary_suppression_reason"]
    assert report["candidate_funnel"]["snapshots"] == 3
    assert report["candidate_funnel"]["entry_candidates"] == report["candidate_count"]
    assert report["opportunity_count"] >= 3
    assert report["candidate_count"] >= 0
    assert report["unique_candidate_ids"] <= report["candidate_count"]
    assert report["semantic_candidate_ids"] == report["unique_candidate_ids"]
    assert report["new_candidates_created"] + report["candidates_carried_forward"] == report["candidate_count"]
    assert report["runtime_reinitializations"] == 1
    assert report["runtime_reinitialization_recoveries"] == 1
    assert report["runtime_reload_success"] is True
    assert report["part3_requests"] == 0
    assert report["real_part3_requests"] == 0
    assert report["duplicate_part3_requests"] == 0
    assert report["duplicate_part3_request_suppressions"] == 0
    assert report["part3_not_requested_reason"]
    assert report["paused_position_monitoring_active"] is True
    assert report["auto_execution_enabled"] is False
    assert report["trade_write_enabled"] is False
    assert report["order_actions"] == 0
    assert report["integrity"]["errors"] == []


def test_harness_reconnect_retries_without_fixture_fallback(tmp_path):
    class FlakyFixture(FixtureSnapshotAdapter):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def capture(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise SnapshotUnavailable("transient terminal unavailable")
            return super().capture(**kwargs)

    report = run_integration_harness(
        output_root=tmp_path,
        adapter=FlakyFixture(),
        iterations=1,
        max_reconnect_attempts=1,
    )
    assert report["snapshots_processed"] == 1
    assert report["reconnect_attempts"] == 1
    assert report["reconnect_successes"] == 1
    assert report["source"] == "FIXTURE"


def test_watcher_tracks_candidate_status_across_snapshot_scoped_ids():
    def state(candidate_id, status):
        return {
            "market_packet": {"snapshot_id": "SNAP_A", "market_packet_id": "MARKET_A", "market_state": [], "active_zones": [], "opportunities": []},
            "scenario_packet": {"scenarios": []},
            "entry_packet": {"candidates": [{
                "candidate_id": candidate_id,
                "scenario_id": "SCN_SR1_BUY_1_SNAP_ANY",
                "entry_type": "STRUCTURED_LIMIT",
                "side": "BUY",
                "entry_range": {"lower": 2000.0, "upper": 2001.0},
                "stop": {"price": 1999.0},
                "trigger": {"mode": "NONE_FOR_LIMIT"},
                "status": status,
            }]},
        }

    result = diff_decision_state(state("ENTRY_A", "WAIT"), state("ENTRY_B", "READY_FOR_PERMISSION_REVIEW"))
    assert [event["event_type"] for event in result["significant_events"]] == ["ENTRY_WINDOW_OPENED"]


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

    timed = dict(base, requested_snapshots=120, snapshots_processed=120)
    assert run_forward_shadow.classify_acceptance(timed) == ("TIMED_FORWARD_SHADOW_PASS", True)

    stalled = dict(base, stopped_reason="SNAPSHOT_STAGE_TIMEOUT:RUN:301.0s")
    assert run_forward_shadow.classify_acceptance(stalled) == ("TIMED_SHADOW_INTERRUPTED_STALL", False)

    fixture = dict(base, source="FIXTURE")
    assert run_forward_shadow.classify_acceptance(fixture) == ("REAL_MT5_VALIDATION_PENDING", False)

    incomplete = dict(base, completed_requested_snapshots=False)
    assert run_forward_shadow.classify_acceptance(incomplete) == ("INCOMPLETE_REQUESTED_SNAPSHOTS", False)
