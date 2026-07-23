from __future__ import annotations

from copy import deepcopy

import pytest

from ctl_analysis_registry.contracts import schema_errors, validate_phase2_payload


def conditional_setup() -> dict:
    return {
        "decision_id": "D1",
        "analysis_id": "A1",
        "view_id": "V1",
        "system": "CHAT_MODEL",
        "decision_type": "SETUP",
        "decision_subtype": "CONDITIONAL_SETUP",
        "prediction_family_id": "PF1",
        "semantic_opportunity_id": "OPP_SCALPING_SELL_G1",
        "variant_id": "EXPLORATORY",
        "symbol": "XAUUSD",
        "direction": "BEARISH",
        "action": "SETUP",
        "role": "PRIMARY",
        "decision_time": "2026-07-23T14:00:00Z",
        "horizons": ["PT30M"],
        "labeling_policy_version": "CONDITIONAL_SINGLE_TARGET_V1",
        "engine_version": "CHAT_SETUP_MATRIX_V1",
        "timeframe_scope": ["M5", "M15"],
        "rules": {
            "success": "SCORING_TARGET_FIRST",
            "failure": "STOP_FIRST",
            "invalidation": {"event_type": "CLOSED_ABOVE", "level": 4058.0},
            "expiry": "2026-07-23T15:00:00Z",
        },
        "market_context": {"regime": "TREND", "volatility": "NORMAL"},
        "source_bindings": {
            "snapshot_id": "S1",
            "manifest_hash": "a" * 64,
            "evidence_hashes": ["b" * 64],
        },
        "quality": {
            "source_qc": "PASS",
            "freshness": "FRESH",
            "integrity_tier": "VERIFIED",
            "scorable_status": "SCORABLE",
        },
        "safety": {
            "trade_write_enabled": False,
            "auto_execution_enabled": False,
            "order_actions": 0,
            "permission_leakage": 0,
        },
        "strictness": "EXPLORATORY",
        "generation_id": "G1",
        "activation": {
            "condition": {
                "event_type": "CLOSED_BELOW",
                "timeframe": "M5",
                "price_field": "MID_CLOSE",
                "level": 4050.0,
            },
            "reference_price_method": "ACTIVATION_BAR_CLOSE_MID",
            "atr_config": {"timeframe": "M5", "period": 14, "method": "WILDER"},
            "expiry_time": "2026-07-23T14:30:00Z",
        },
        "setup_geometry": {
            "side": "SELL",
            "entry": 4050.0,
            "stop": 4058.0,
            "scoring_target": 4040.0,
            "expiry_time": "2026-07-23T15:00:00Z",
        },
        "geometry_provenance": {
            "zone_id": "ZONE_M5_SUPPLY_1",
            "zone_lower": 4050.0,
            "zone_upper": 4056.0,
            "buffer_method": "SPREAD_PLUS_ATR_FRACTION",
            "policy_version": "FOUR_TIER_GEOMETRY_V1",
        },
    }


def test_conditional_setup_contract_accepts_complete_decision() -> None:
    assert schema_errors("frozen_model_decision.schema.json", conditional_setup()) == []
    assert validate_phase2_payload("DECISION_FROZEN", conditional_setup()) == []


@pytest.mark.parametrize(
    "field",
    ["activation", "setup_geometry", "strictness", "generation_id", "geometry_provenance"],
)
def test_conditional_setup_contract_rejects_missing_required_field(field: str) -> None:
    payload = deepcopy(conditional_setup())
    payload.pop(field)

    errors = validate_phase2_payload("DECISION_FROZEN", payload)

    assert any(field in error for error in errors)


def test_conditional_setup_contract_rejects_unknown_strictness() -> None:
    payload = conditional_setup()
    payload["strictness"] = "ULTRA"

    errors = validate_phase2_payload("DECISION_FROZEN", payload)

    assert any("strictness" in error for error in errors)
