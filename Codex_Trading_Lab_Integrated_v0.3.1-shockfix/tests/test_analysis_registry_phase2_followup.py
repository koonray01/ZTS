from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from ctl_analysis_registry.followup import (
    EvidenceCollisionError,
    collect_followup,
    cross_snapshot_qc,
    eligible_bars,
    reconstruct_prices,
    select_terminal_bar,
)
from ctl_mt5_snapshot.adapter import MetaTrader5SnapshotAdapter


def _job(**overrides) -> dict:
    job = {
        "job_id": "JOB_1", "decision_id": "DECISION_1", "horizon": "PT1H",
        "evaluation_start": "2026-07-22T10:03:00Z",
        "evaluation_deadline": "2026-07-22T11:03:00Z", "timeframe": "M5",
        "max_terminal_lag_seconds": 300,
        "symbol": "XAUUSD",
        "source_binding": {
            "source": "LIVE_MT5", "server": "TEST-SERVER", "symbol": "XAUUSD",
            "digits": 2, "point": 0.01, "broker_utc_offset_minutes": 0,
            "overlap_fingerprint": "aaa",
        },
        "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0},
    }
    job.update(overrides)
    return job


def _bar(open_time: str, close_time: str, **overrides) -> dict:
    bar = {
        "bar_id": f"BAR_{open_time}", "timeframe": "M5", "open_time": open_time,
        "close_time": close_time, "open": 100.0, "high": 102.0, "low": 99.0,
        "close": 101.0, "spread_points": 10, "is_closed": True,
    }
    bar.update(overrides)
    return bar


def test_bar_containing_evaluation_start_is_excluded() -> None:
    bars = [
        _bar("2026-07-22T10:00:00Z", "2026-07-22T10:05:00Z"),
        _bar("2026-07-22T10:05:00Z", "2026-07-22T10:10:00Z"),
    ]

    assert [bar["open_time"] for bar in eligible_bars(_job(), bars)] == ["2026-07-22T10:05:00Z"]


def test_weekend_bar_outside_terminal_lag_is_not_used() -> None:
    job = _job(
        evaluation_deadline="2026-07-24T21:00:00Z",
        max_terminal_lag_seconds=300,
    )
    result = select_terminal_bar(
        job,
        [_bar("2026-07-26T22:00:00Z", "2026-07-26T22:05:00Z")],
    )

    assert result == {"status": "INSUFFICIENT_FOLLOWUP", "reason": "MARKET_CLOSURE_NO_TERMINAL_BAR"}


def test_changed_overlap_fingerprint_blocks_outcome() -> None:
    evidence = {"source_binding": {**_job()["source_binding"], "overlap_fingerprint": "bbb"}}

    qc = cross_snapshot_qc(_job()["source_binding"], evidence)

    assert qc["status"] == "FAIL"
    assert "EVIDENCE_CONFLICT" in qc["reasons"]


def test_valid_spread_reconstructs_ask_and_mid_cohort() -> None:
    result = reconstruct_prices([_bar("2026-07-22T10:05:00Z", "2026-07-22T10:10:00Z")], point=0.01, ticks=[])

    assert result["price_quality"] == "BAR_SPREAD_RECONSTRUCTED"
    assert result["bars"][0]["ask_high"] == 102.1
    assert result["bars"][0]["mid_close"] == 101.05


def test_missing_spread_is_mid_only_proxy() -> None:
    bar = _bar("2026-07-22T10:05:00Z", "2026-07-22T10:10:00Z", spread_points=None)

    result = reconstruct_prices([bar], point=0.01, ticks=[])

    assert result["price_quality"] == "MID_ONLY_PROXY"
    assert "ask_close" not in result["bars"][0]


class _Adapter:
    def __init__(self):
        self.calls = []

    def closed_bars_between(self, symbol, timeframe, start, end):
        self.calls.append(("bars", symbol, timeframe, start, end))
        return [
            _bar("2026-07-22T10:05:00Z", "2026-07-22T10:10:00Z"),
            _bar("2026-07-22T11:00:00Z", "2026-07-22T11:05:00Z"),
        ]

    def ticks_between(self, symbol, start, end):
        self.calls.append(("ticks", symbol, start, end))
        return []


def test_collect_followup_persists_hashed_immutable_bundle(tmp_path: Path) -> None:
    adapter = _Adapter()

    evidence = collect_followup(_job(), adapter, tmp_path)

    bundle = tmp_path / "JOB_1"
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert evidence["price_quality"] == "BAR_SPREAD_RECONSTRUCTED"
    assert manifest["job_id"] == "JOB_1"
    assert len(manifest["raw_hashes"]["bars.json"]) == 64
    assert evidence["safety"]["order_actions"] == 0
    assert [call[0] for call in adapter.calls] == ["bars", "ticks"]


def test_followup_bundle_rejects_different_content_for_same_job(tmp_path: Path) -> None:
    adapter = _Adapter()
    collect_followup(_job(), adapter, tmp_path)
    adapter.closed_bars_between = lambda *args: [
        _bar("2026-07-22T10:05:00Z", "2026-07-22T10:10:00Z", close=999.0)
    ]

    with pytest.raises(EvidenceCollisionError):
        collect_followup(_job(), adapter, tmp_path)


class _FakeMT5:
    TIMEFRAME_M5 = 5
    COPY_TICKS_ALL = 7

    def __init__(self):
        self.calls = []

    def initialize(self):
        self.calls.append("initialize")
        return True

    def shutdown(self):
        self.calls.append("shutdown")

    def symbol_select(self, symbol, enabled):
        self.calls.append(("symbol_select", symbol, enabled))
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=1784707200, bid=100.0, ask=100.1)

    def copy_rates_range(self, symbol, timeframe, start, end):
        self.calls.append(("copy_rates_range", symbol, timeframe, start, end))
        class NonJsonInteger:
            def __int__(self):
                return 10

        return [{"time": 1784707200, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "tick_volume": 10, "real_volume": 1, "spread": NonJsonInteger()}]

    def copy_ticks_range(self, symbol, start, end, flags):
        self.calls.append(("copy_ticks_range", symbol, start, end, flags))
        return [{"time_msc": 1784707200123, "bid": 100.0, "ask": 100.1, "last": 100.05, "volume": 1}]

    def last_error(self):
        return (0, "OK")


def test_mt5_history_methods_are_read_only_and_normalized() -> None:
    mt5 = _FakeMT5()
    adapter = MetaTrader5SnapshotAdapter(mt5)
    start = datetime(2026, 7, 22, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)

    bars = adapter.closed_bars_between("XAUUSD", "M5", start, end)
    ticks = adapter.ticks_between("XAUUSD", start, end)

    assert bars[0]["timeframe"] == "M5"
    assert bars[0]["is_closed"] is True
    assert bars[0]["spread_points"] == 10
    json.dumps(bars)
    assert ticks[0]["bid"] == 100.0 and ticks[0]["ask"] == 100.1
    assert any(isinstance(call, tuple) and call[0] == "copy_rates_range" for call in mt5.calls)
    assert any(isinstance(call, tuple) and call[0] == "copy_ticks_range" for call in mt5.calls)
    assert not any(isinstance(call, tuple) and call[0].startswith("order") for call in mt5.calls)
