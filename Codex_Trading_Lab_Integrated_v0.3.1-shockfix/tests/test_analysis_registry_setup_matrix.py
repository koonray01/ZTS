from __future__ import annotations

from ctl_analysis_registry.setup_matrix import (
    STRICTNESS,
    build_four_tier_setup_envelope,
    setup_matrix_summary,
)


def _snapshot() -> dict:
    return {
        "snapshot_id": "SNAP_MATRIX_1",
        "symbol": "XAUUSD",
        "source": "LIVE_MT5",
        "capture_time": "2026-07-23T14:00:00Z",
        "quote": {"bid": 4049.9, "ask": 4050.1},
        "qc": {"decision": "PASS"},
        "freshness": {"status": "FRESH"},
        "evidence_refs": ["EVID_MATRIX_1"],
        "terminal": {"connected": True, "trade_write_enabled": False},
    }


def _decision_state() -> dict:
    return {
        "snapshot_id": "SNAP_MATRIX_1",
        "market_packet": {
            "risk_flags": [],
            "market_state": [
                {"timeframe": "M5", "regime": "TREND", "structure": "BEARISH", "volatility": "NORMAL"},
                {"timeframe": "M15", "regime": "TREND", "structure": "BEARISH", "volatility": "NORMAL"},
                {"timeframe": "H1", "regime": "TREND", "structure": "BEARISH", "volatility": "NORMAL"},
                {"timeframe": "H4", "regime": "RANGE", "structure": "TRANSITION", "volatility": "NORMAL"},
            ],
            "active_zones": [
                {"zone_id": "M5_DEMAND", "timeframe": "M5", "zone_type": "DEMAND", "lower": 4038.0, "upper": 4040.0, "status": "ACTIVE"},
                {"zone_id": "M5_SUPPLY", "timeframe": "M5", "zone_type": "SUPPLY", "lower": 4052.0, "upper": 4054.0, "status": "ACTIVE"},
                {"zone_id": "M15_DEMAND", "timeframe": "M15", "zone_type": "DEMAND", "lower": 4028.0, "upper": 4031.0, "status": "ACTIVE"},
                {"zone_id": "M15_SUPPLY", "timeframe": "M15", "zone_type": "SUPPLY", "lower": 4060.0, "upper": 4063.0, "status": "ACTIVE"},
                {"zone_id": "H1_DEMAND", "timeframe": "H1", "zone_type": "DEMAND", "lower": 4010.0, "upper": 4015.0, "status": "ACTIVE"},
                {"zone_id": "H1_SUPPLY", "timeframe": "H1", "zone_type": "SUPPLY", "lower": 4080.0, "upper": 4085.0, "status": "ACTIVE"},
                {"zone_id": "H4_DEMAND", "timeframe": "H4", "zone_type": "DEMAND", "lower": 3990.0, "upper": 4000.0, "status": "ACTIVE"},
                {"zone_id": "H4_SUPPLY", "timeframe": "H4", "zone_type": "SUPPLY", "lower": 4100.0, "upper": 4110.0, "status": "ACTIVE"},
            ],
        },
    }


def test_matrix_contains_sixteen_variants() -> None:
    envelope = build_four_tier_setup_envelope(_snapshot(), _decision_state())
    claims = envelope["claims"]

    assert len(claims) == 16
    assert {claim["strictness"] for claim in claims} == set(STRICTNESS)
    assert {claim["setup_horizon"] for claim in claims} == {"SCALPING", "DAYTRADE"}
    assert {claim["side"] for claim in claims} == {"BUY", "SELL"}


def test_strictness_variants_share_semantic_opportunity() -> None:
    claims = build_four_tier_setup_envelope(_snapshot(), _decision_state())["claims"]
    scalp_sell = [
        claim
        for claim in claims
        if claim["setup_horizon"] == "SCALPING" and claim["side"] == "SELL"
    ]

    assert len({claim["semantic_opportunity_id"] for claim in scalp_sell}) == 1
    assert {claim["variant_id"] for claim in scalp_sell} == set(STRICTNESS)


def test_geometry_is_side_correct_and_meets_strictness_floor() -> None:
    claims = build_four_tier_setup_envelope(_snapshot(), _decision_state())["claims"]

    for claim in claims:
        assert claim["scorable_hint"] is True
        risk = abs(claim["entry"] - claim["stop"])
        reward = abs(claim["scoring_target"] - claim["entry"])
        assert reward / risk >= STRICTNESS[claim["strictness"]]["min_rr"]
        if claim["side"] == "BUY":
            assert claim["stop"] < claim["entry"] < claim["scoring_target"]
        else:
            assert claim["scoring_target"] < claim["entry"] < claim["stop"]


def test_activation_grammar_strengthens_monotonically() -> None:
    claims = build_four_tier_setup_envelope(_snapshot(), _decision_state())["claims"]
    sell = {
        claim["strictness"]: claim
        for claim in claims
        if claim["setup_horizon"] == "SCALPING" and claim["side"] == "SELL"
    }

    assert sell["EXPLORATORY"]["activation_policy"]["required_events"] == 1
    assert sell["VERY_RELAXED"]["activation_policy"]["required_events"] == 2
    assert sell["RELAXED"]["activation_policy"]["required_events"] == 3
    assert sell["NORMAL"]["activation_policy"]["required_events"] == 4


def test_summary_counts_scorable_and_non_scorable() -> None:
    summary = setup_matrix_summary(
        build_four_tier_setup_envelope(_snapshot(), _decision_state())
    )

    assert summary == {
        "setup_class": "CONDITIONAL_WATCH_SETUP",
        "generation_id": summary["generation_id"],
        "variant_count": 16,
        "scorable_count": 16,
        "non_scorable_count": 0,
    }


def test_blocking_risk_returns_no_setup() -> None:
    decision = _decision_state()
    decision["market_packet"]["risk_flags"] = [
        {"code": "SHOCK_H1", "severity": "BLOCK", "message": "shock"}
    ]

    envelope = build_four_tier_setup_envelope(_snapshot(), decision)

    assert envelope["claims"] == []
    assert envelope["setup_class"] == "NO_SETUP"
    assert envelope["block_reasons"] == ["SHOCK_H1"]
