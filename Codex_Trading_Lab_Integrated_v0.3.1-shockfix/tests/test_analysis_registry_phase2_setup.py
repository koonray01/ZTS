from __future__ import annotations

from ctl_analysis_registry.setup import label_setup, refine_same_bar


def _setup(*, side="BUY", entry=100.0, stop=99.0, target=102.0):
    return {
        "decision_id": "SETUP_1", "system": "ZENITH", "decision_type": "SETUP",
        "labeling_policy_version": "SINGLE_TARGET",
        "setup_geometry": {
            "side": side, "entry": entry, "stop": stop,
            "scoring_target": target, "expiry_time": "2026-07-22T11:00:00Z",
        },
        "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0},
    }


def _evidence(bars, *, quality="BAR_SPREAD_RECONSTRUCTED", m1=None, ticks=None):
    return {
        "evidence_id": "EVIDENCE_1", "price_quality": quality, "bars": bars,
        "m1_bars": m1 or [], "ticks": ticks or [],
        "qc": {"status": "PASS", "reasons": []}, "evidence_refs": ["EVIDENCE_1"],
    }


def test_buy_entry_uses_ask_and_target_uses_bid() -> None:
    bars = [
        {"bar_id": "B1", "ask_low": 100.0, "bid_high": 101.0, "bid_low": 99.5, "close_time": "2026-07-22T10:05:00Z"},
        {"bar_id": "B2", "ask_low": 100.5, "bid_high": 102.0, "bid_low": 100.2, "close_time": "2026-07-22T10:10:00Z"},
    ]

    result = label_setup(_setup(), _evidence(bars))

    assert result["classification"] == "TP_FIRST"
    assert result["realized_r"] == 2.0


def test_sell_entry_uses_bid_and_target_uses_ask() -> None:
    bars = [
        {"bar_id": "B1", "bid_high": 100.0, "ask_low": 99.5, "ask_high": 100.5, "close_time": "2026-07-22T10:05:00Z"},
        {"bar_id": "B2", "bid_high": 99.5, "ask_low": 98.0, "ask_high": 99.7, "close_time": "2026-07-22T10:10:00Z"},
    ]

    assert label_setup(_setup(side="SELL", stop=101.0, target=98.0), _evidence(bars))["classification"] == "TP_FIRST"


def test_one_m1_bar_touching_tp_and_sl_stays_ambiguous() -> None:
    source = [{"bar_id": "B1", "ask_low": 100.0, "bid_high": 102.0, "bid_low": 99.0, "close_time": "2026-07-22T10:05:00Z"}]
    m1 = [{"bar_id": "M1", "ask_low": 100.0, "bid_high": 102.0, "bid_low": 99.0, "close_time": "2026-07-22T10:01:00Z"}]

    result = label_setup(_setup(), _evidence(source, m1=m1))

    assert result["classification"] == "AMBIGUOUS_SAME_BAR"


def test_m1_refinement_proves_target_before_stop() -> None:
    source = [{"bar_id": "B1", "ask_low": 100.0, "bid_high": 102.0, "bid_low": 99.0, "close_time": "2026-07-22T10:05:00Z"}]
    m1 = [
        {"bar_id": "M1A", "ask_low": 100.0, "bid_high": 102.0, "bid_low": 99.5, "close_time": "2026-07-22T10:01:00Z"},
        {"bar_id": "M1B", "ask_low": 100.5, "bid_high": 101.0, "bid_low": 99.0, "close_time": "2026-07-22T10:02:00Z"},
    ]

    assert refine_same_bar(_setup(), _evidence(source, m1=m1))["classification"] == "TP_FIRST"


def test_true_ticks_refine_m1_same_bar_order() -> None:
    source = [{"bar_id": "B1", "ask_low": 100.0, "bid_high": 102.0, "bid_low": 99.0, "close_time": "2026-07-22T10:05:00Z"}]
    m1 = [{"bar_id": "M1", "ask_low": 100.0, "bid_high": 102.0, "bid_low": 99.0, "close_time": "2026-07-22T10:01:00Z"}]
    ticks = [
        {"tick_time": "2026-07-22T10:00:01Z", "bid": 99.9, "ask": 100.0},
        {"tick_time": "2026-07-22T10:00:02Z", "bid": 102.0, "ask": 102.1},
        {"tick_time": "2026-07-22T10:00:03Z", "bid": 99.0, "ask": 99.1},
    ]

    result = label_setup(_setup(), _evidence(source, quality="TRUE_BID_ASK_TICKS", m1=m1, ticks=ticks))
    assert result["classification"] == "TP_FIRST"


def test_mid_only_proxy_cannot_resolve_setup() -> None:
    result = label_setup(_setup(), _evidence([], quality="MID_ONLY_PROXY"))
    assert result["classification"] == "INVALID_INPUT"
    assert "MID_ONLY_PROXY" in result["reason_codes"]


def test_untouched_entry_expires_untriggered() -> None:
    bars = [{"bar_id": "B1", "ask_low": 101.0, "bid_high": 101.5, "bid_low": 100.5, "close_time": "2026-07-22T11:05:00Z"}]
    result = label_setup(_setup(), _evidence(bars))
    assert result["classification"] == "EXPIRED_UNTRIGGERED"
