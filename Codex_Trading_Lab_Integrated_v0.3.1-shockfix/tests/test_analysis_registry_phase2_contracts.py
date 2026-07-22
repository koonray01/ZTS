from __future__ import annotations

from copy import deepcopy

import pytest

from ctl_analysis_registry.contracts import (
    PHASE2_EVENT_TYPES,
    V2_SCHEMA_VERSION,
    validate_phase2_payload,
)
from ctl_analysis_registry.events import build_event, build_v2_event, validate_event_chain


def _event_fields(event_id: str, event_type: str, payload: dict) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "event_time": "2026-07-22T09:00:00Z",
        "decision_time": "2026-07-22T09:00:00Z",
        "source_class": "LIVE_MT5",
        "integrity_tier": "VERIFIED",
        "producer": "phase2-test",
        "payload": payload,
    }


def _frozen_directional(*, conditional: bool = False) -> dict:
    decision = {
        "decision_id": "DECISION_CHAT_1",
        "analysis_id": "ANALYSIS_1",
        "view_id": "VIEW_CHAT_1",
        "system": "CHAT_MODEL",
        "decision_type": "DIRECTIONAL",
        "decision_subtype": "CONDITIONAL_DIRECTIONAL" if conditional else "UNCONDITIONAL_DIRECTIONAL",
        "prediction_family_id": "PRED_CHAT_XAUUSD_DIRECTION",
        "semantic_opportunity_id": "OPPORTUNITY_XAUUSD_1",
        "variant_id": "BASE",
        "symbol": "XAUUSD",
        "direction": "BULLISH",
        "action": "WATCH" if conditional else "HOLD",
        "role": "PRIMARY",
        "decision_time": "2026-07-22T09:00:00Z",
        "horizons": ["PT15M", "PT1H"],
        "labeling_policy_version": "DIRECTIONAL_TERMINAL_ATR_V1",
        "engine_version": "CHAT_MODEL_TEST_V1",
        "timeframe_scope": ["M5", "M15", "H1", "H4"],
        "rules": {
            "success": "SIGNED_RETURN_ATR_GTE_0_25",
            "failure": "SIGNED_RETURN_ATR_LTE_NEG_0_25",
            "invalidation": "SOURCE_BINDING_INVALID",
            "expiry": "HORIZON_END",
        },
        "market_context": {
            "regime": "RANGE",
            "volatility": "NORMAL",
        },
        "source_bindings": {
            "snapshot_id": "SNAP_1",
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
    }
    if conditional:
        decision["activation"] = {
            "condition": {
                "event_type": "CLOSED_ABOVE",
                "timeframe": "M15",
                "price_field": "MID_CLOSE",
                "level": 4025.0,
            },
            "reference_price_method": "ACTIVATION_BAR_CLOSE_MID",
            "atr_config": {"timeframe": "M15", "period": 14, "method": "WILDER"},
            "expiry_time": "2026-07-22T12:00:00Z",
        }
    else:
        decision["reference_price"] = {"method": "DECISION_TIME_MID", "value": 4018.5}
        decision["atr"] = {"timeframe": "M15", "period": 14, "method": "WILDER", "value": 4.0}
    return decision


def test_v1_and_v2_events_share_one_valid_hash_chain() -> None:
    v1 = build_event(
        _event_fields("EVENT_V1", "ANALYSIS_RECORDED", {"analysis_id": "ANALYSIS_1"}),
        previous_hash=None,
    )
    decision = _frozen_directional(conditional=True)
    v2 = build_v2_event(
        _event_fields("EVENT_V2", "DECISION_FROZEN", decision),
        previous_hash=v1["event_hash"],
    )

    assert v2["schema_version"] == V2_SCHEMA_VERSION
    assert validate_event_chain([v1, v2]) == []
    assert validate_phase2_payload("DECISION_FROZEN", decision) == []


def test_conditional_contract_requires_activation_method_and_atr_config() -> None:
    decision = _frozen_directional(conditional=True)
    decision.pop("activation")

    errors = validate_phase2_payload("DECISION_FROZEN", decision)

    assert any("activation is required" in error for error in errors)


def test_unconditional_contract_requires_decision_time_reference_and_atr() -> None:
    decision = _frozen_directional()
    decision.pop("reference_price")
    decision.pop("atr")

    errors = validate_phase2_payload("DECISION_FROZEN", decision)

    assert any("reference_price is required" in error for error in errors)
    assert any("atr is required" in error for error in errors)


def test_frozen_decision_rejects_trading_safety_leakage() -> None:
    decision = deepcopy(_frozen_directional())
    decision["safety"]["trade_write_enabled"] = True

    errors = validate_phase2_payload("DECISION_FROZEN", decision)

    assert any("trade_write_enabled" in error for error in errors)


def test_phase2_event_names_are_frozen() -> None:
    assert PHASE2_EVENT_TYPES == {
        "DECISION_FROZEN",
        "EVALUATION_JOB_SCHEDULED",
        "DECISION_ACTIVATED",
        "FOLLOWUP_EVIDENCE_RECORDED",
        "MODEL_OUTCOME_RECORDED",
        "REPORT_PUBLISHED",
    }


def test_v2_constructor_rejects_phase1_event_name() -> None:
    with pytest.raises(ValueError, match="Phase 2 event type"):
        build_v2_event(
            _event_fields("EVENT_BAD", "ANALYSIS_RECORDED", {"analysis_id": "ANALYSIS_1"}),
            previous_hash=None,
        )


def _safety() -> dict:
    return {
        "trade_write_enabled": False,
        "auto_execution_enabled": False,
        "order_actions": 0,
        "permission_leakage": 0,
    }


def test_job_evidence_and_outcome_payload_schemas_dispatch() -> None:
    job = {
        "job_id": "JOB_1",
        "decision_id": "DECISION_CHAT_1",
        "horizon": "PT15M",
        "labeling_policy_version": "DIRECTIONAL_TERMINAL_ATR_V1",
        "state": "PENDING",
        "due_at": "2026-07-22T09:15:00Z",
        "safety": _safety(),
    }
    evidence = {
        "evidence_id": "EVIDENCE_1",
        "decision_id": "DECISION_CHAT_1",
        "horizon": "PT15M",
        "symbol": "XAUUSD",
        "source_binding": {"snapshot_id": "SNAP_1", "source": "LIVE_MT5"},
        "bars": [],
        "qc": {"decision": "PASS"},
        "price_quality": "MID_ONLY_PROXY",
        "manifest_hash": "a" * 64,
        "safety": _safety(),
    }
    outcome = {
        "outcome_id": "OUTCOME_1",
        "decision_id": "DECISION_CHAT_1",
        "decision_type": "DIRECTIONAL",
        "system": "CHAT_MODEL",
        "horizon": "PT15M",
        "original_policy_version": "DIRECTIONAL_TERMINAL_ATR_V1",
        "classification": "NEUTRAL",
        "evidence_refs": ["EVIDENCE_1"],
        "safety": _safety(),
    }

    assert validate_phase2_payload("EVALUATION_JOB_SCHEDULED", job) == []
    assert validate_phase2_payload("FOLLOWUP_EVIDENCE_RECORDED", evidence) == []
    assert validate_phase2_payload("MODEL_OUTCOME_RECORDED", outcome) == []
