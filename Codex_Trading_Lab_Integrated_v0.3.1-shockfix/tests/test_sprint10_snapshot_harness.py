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
from ctl_live_runtime import LiveRuntime
from ctl_mt5_snapshot.harness import _candidate_suppression_breakdown, _market_state_hash


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


def test_mt5_adapter_normalizes_broker_server_time_offset():
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
        symbol_info_tick=lambda _symbol: SimpleNamespace(time=int(broker_now.timestamp()), bid=100.0, ask=100.2, last=100.1),
        positions_get=lambda symbol: [],
        copy_rates_from_pos=lambda _symbol, timeframe, _start, _bars: rows_for({5: 5, 15: 15, 60: 60, 240: 240}[timeframe]),
        last_error=lambda: None,
    )
    adapter = MetaTrader5SnapshotAdapter(mt5_module=fake)
    snapshot = adapter.capture(symbol="XAUUSD", run_id="RUN-OFFSET", bars=2)
    assert snapshot["broker_utc_offset_minutes"] > 0
    latest_close = snapshot["timeframes"][0]["bars"][-1]["close_time"]
    assert latest_close <= snapshot["capture_time"]


def test_qc_quarantines_disconnected_or_stale_live_mt5_tick():
    snapshot = FixtureSnapshotAdapter().capture(symbol="XAUUSD", run_id="RUN-LIVE-QC-001", bars=20)
    snapshot["source"] = "LIVE_MT5"
    snapshot["terminal"]["connected"] = False
    snapshot["last_tick_time"] = "2025-03-10T11:50:00Z"
    snapshot["capture_time"] = "2025-03-10T12:00:00Z"
    result = validate_snapshot_qc(snapshot, now=datetime(2025, 3, 10, 12, 0, 0, tzinfo=timezone.utc))
    assert result["qc"]["decision"] == "QUARANTINE"
    assert "not connected" in " ".join(result["qc"]["errors"])
    assert "tick is stale" in " ".join(result["qc"]["errors"])


def test_qc_quarantines_duplicate_timeframe_and_incomplete_coverage():
    snapshot = FixtureSnapshotAdapter().capture(symbol="XAUUSD", run_id="RUN-COVERAGE-QC-001", bars=20)
    snapshot["timeframes"].append(copy.deepcopy(snapshot["timeframes"][0]))
    snapshot["timeframes"][1]["returned_bars"] = 19
    result = validate_snapshot_qc(snapshot)
    assert result["qc"]["decision"] == "QUARANTINE"
    text = " ".join(result["qc"]["errors"])
    assert "Duplicate timeframe" in text
    assert "fewer bars" in text


def test_runtime_requires_healthy_snapshot_before_active(tmp_path):
    runtime = LiveRuntime(tmp_path, "XAUUSD", require_live_source=False)
    started = runtime.start(now=datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc))
    assert started["state"] == "STARTING"
    assert started["new_entries_allowed"] is False

    snapshot = FixtureSnapshotAdapter().capture(symbol="XAUUSD", run_id="RUN-RUNTIME-HEALTHY", bars=20)
    result = runtime.process_snapshot(snapshot, now=datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc))
    assert result["session"]["state"] == "ACTIVE"
    assert result["session"]["new_entries_allowed"] is True


def test_live_runtime_locks_when_snapshot_source_is_not_live_mt5(tmp_path):
    runtime = LiveRuntime(tmp_path, "XAUUSD")
    runtime.start(now=datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc))
    snapshot = FixtureSnapshotAdapter().capture(symbol="XAUUSD", run_id="RUN-RUNTIME-FIXTURE", bars=20)
    result = runtime.process_snapshot(snapshot, now=datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc))
    assert result["health"]["status"] == "CRITICAL"
    assert "SNAPSHOT_SOURCE_NOT_LIVE_MT5" in result["session"]["active_locks"]
    assert result["session"]["new_entries_allowed"] is False


def test_shadow_hash_and_suppression_use_packet_data_quality(snapshot):
    decision = __import__("ctl_decision_core").run_decision_core(snapshot)
    baseline = _market_state_hash(decision)
    changed = copy.deepcopy(decision)
    changed["market_packet"]["risk_flags"].append(
        {"code": "SHOCK_M5", "severity": "BLOCK", "message": "Test shock", "evidence_refs": ["EVID_TEST"]}
    )
    assert _market_state_hash(changed) != baseline

    changed["market_packet"]["data_quality"]["freshness"] = "STALE"
    suppression = _candidate_suppression_breakdown(changed)
    assert suppression["STALE_DATA_BLOCK"] == 1


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


def test_full_pipeline_identity_harness_and_restart_recovery(tmp_path):
    report = run_integration_harness(output_root=tmp_path, iterations=3)
    assert report["final_decision"] == "CONDITIONAL_GO_PENDING_REAL_MT5"
    assert report["snapshots_processed"] == 3
    assert report["candidate_count"] == report["ready_candidate_count"] + report["wait_candidate_count"] + report["rejected_candidate_count"] + report["expired_candidate_count"]
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
    assert report["paused_position_monitoring_active"] is True
    assert report["auto_execution_enabled"] is False
    assert report["trade_write_enabled"] is False
    assert report["order_actions"] == 0
    assert report["integrity"]["errors"] == []


def test_forward_harness_exposes_per_snapshot_tfi_source_provider():
    parameters = inspect.signature(run_integration_harness).parameters
    assert "tfi_shadow_source_provider" in parameters


def test_forward_harness_attaches_fresh_tfi_from_provider_without_authority_change(tmp_path):
    tfi_path = tmp_path / "fresh_tfi.json"
    tfi_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "schema_ref": "brain/output_schema/tfi_snapshot.schema.json",
                "run_id": "TFI-FORWARD-TEST",
                "timestamp_utc": "2025-03-10T11:59:00Z",
                "evaluation_end_utc": "2025-03-10T11:45:00Z",
                "bar_close_utc": "2025-03-10T11:45:00Z",
                "data_qc": {"status": "PASS"},
                "market_board": [
                    {"symbol": "XAUUSD", "evidence_family": "gold_precious_metals", "quality": "FRESH", "return_pct": 0.2, "source_snapshot_id": "XAU-1", "freshness_threshold_seconds": 1020},
                    {"symbol": "EURUSD", "evidence_family": "broad_usd_fx", "quality": "FRESH", "return_pct": -0.1, "source_snapshot_id": "EUR-1", "freshness_threshold_seconds": 1020},
                    {"symbol": "USDJPY", "evidence_family": "jpy_cross_breadth", "quality": "FRESH", "return_pct": -0.1, "source_snapshot_id": "JPY-1", "freshness_threshold_seconds": 1020},
                ],
                "manifest": {"run_id": "TFI-FORWARD-TEST", "config_hash": "A" * 64},
                "execution_impact": "none",
                "can_execute": False,
            }
        ),
        encoding="utf-8",
    )
    calls = 0

    def provider():
        nonlocal calls
        calls += 1
        return tfi_path

    report = run_integration_harness(
        output_root=tmp_path / "run",
        iterations=1,
        tfi_shadow_source_provider=provider,
    )
    decision_path = tmp_path / "run" / "runtime" / "outputs" / report["snapshots"][0]["snapshot_id"] / "decision_state.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    shadow = decision["advisory_shadow"]

    assert calls == 1
    assert shadow["status"] == "SHADOW_ACCEPTED"
    assert shadow["tfi_context"]["status"] == "OBSERVATION_ONLY"
    assert shadow["authority_hash_before"] == shadow["authority_hash_after"]
    assert shadow["candidate_permission_invariant"] is True
    assert shadow["order_actions"] == shadow["permission_leakage"] == shadow["tfi_permission_override"] == 0
    assert report["tfi_context_attached_snapshots"] == 1
    assert report["tfi_context_observation_only_snapshots"] == 1
    assert report["tfi_context_unknown_snapshots"] == 0


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


def test_forward_shadow_exposes_tradingos_tfi_provider(root):
    sys.path.insert(0, str(root / "tools"))
    import run_forward_shadow

    assert hasattr(run_forward_shadow, "build_tradingos_tfi_provider")


def test_tradingos_tfi_provider_refreshes_and_returns_safe_fresh_snapshot(root, tmp_path):
    sys.path.insert(0, str(root / "tools"))
    import run_forward_shadow

    trading_os = tmp_path / "trading_os"
    trading_os.mkdir()
    (trading_os / "trade.py").write_text("# test entrypoint\n", encoding="utf-8")
    latest = trading_os / "data" / "tfi" / "snapshots" / "latest_snapshot.json"
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        if "analyze" in command:
            latest.parent.mkdir(parents=True, exist_ok=True)
            latest.write_text(
                json.dumps(
                    {
                        "timestamp_utc": "2026-07-16T10:29:35Z",
                        "evaluation_end_utc": "2026-07-16T10:15:00Z",
                        "data_qc": {"status": "PASS"},
                        "market_board": [
                            {"symbol": "XAUUSD", "quality": "FRESH"},
                            {"symbol": "EURUSD", "quality": "FRESH"},
                            {"symbol": "USDJPY", "quality": "FRESH"},
                        ],
                        "execution_impact": "none",
                        "can_execute": False,
                    }
                ),
                encoding="utf-8",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    provider = run_forward_shadow.build_tradingos_tfi_provider(
        trading_os,
        python_executable="python-test",
        refresh_attempts=1,
        command_runner=runner,
    )

    assert Path(provider()) == latest
    assert [call[0][3] for call in calls] == ["collect", "analyze"]
    assert all(call[1]["cwd"] == trading_os for call in calls)
    assert all(call[1]["encoding"] == "utf-8" and call[1]["errors"] == "replace" for call in calls)
