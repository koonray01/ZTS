from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from ctl_analysis_registry.chat_model import freeze_chat_model_view
from ctl_analysis_registry.ledger import AppendOnlyLedger
from ctl_analysis_registry.recorder import (
    freeze_zenith_decisions,
    record_frozen_decisions,
    revise_decision,
)


NOW = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)


def _snapshot() -> dict:
    return {
        "snapshot_id": "SNAP_1", "symbol": "XAUUSD", "source": "LIVE_MT5",
        "capture_time": NOW.isoformat(), "quote": {"bid": 4018.4, "ask": 4018.6},
        "qc": {"decision": "PASS"}, "freshness": {"status": "FRESH"},
        "evidence_refs": ["SNAP_1", "BARS_1"],
    }


def _decision_state() -> dict:
    return {
        "snapshot_id": "SNAP_1",
        "engine_version": "ZENITH_TEST_V1",
        "market_packet": {"regime": "RANGE", "volatility": "NORMAL", "atr": {"M15": 4.0}},
        "scenario_packet": {
            "scenarios": [
                {
                    "scenario_id": "SCENARIO_1", "rank": "PRIMARY", "direction": "BULLISH",
                    "status": "WATCHING", "horizons": ["PT1H"],
                    "event_steps": [
                        {"step_id": "S1", "sequence": 1, "event_type": "CLOSED_ABOVE", "timeframe": "M15", "level": 4025.0, "price_field": "MID_CLOSE", "required": True}
                    ],
                    "invalidation": {"event_type": "CLOSED_BELOW", "timeframe": "M15", "level": 4008.0},
                    "expiry_time": "2026-07-22T12:00:00+00:00",
                }
            ]
        },
        "entry_packet": {"candidates": []},
    }


def _chat_envelope() -> dict:
    return {
        "analysis_id": "ANALYSIS_CHAT_1", "view_id": "VIEW_CHAT_1",
        "snapshot_id": "SNAP_1", "system": "CHAT_MODEL",
        "engine_version": "CHAT_MODEL_TEST_V1",
        "claims": [
            {
                "claim_id": "CLAIM_1", "decision_type": "DIRECTIONAL",
                "decision_subtype": "UNCONDITIONAL_DIRECTIONAL", "direction": "BULLISH",
                "action": "WATCH", "role": "PRIMARY", "horizons": ["PT1H"],
                "timeframe_scope": ["M15", "H1"], "reference_price": 4018.5,
                "atr": {"timeframe": "M15", "period": 14, "method": "WILDER", "value": 4.0},
            }
        ],
    }


def test_zenith_and_chat_model_have_separate_system_ids() -> None:
    zenith = freeze_zenith_decisions(_decision_state(), _snapshot(), "ANALYSIS_1")
    chat = freeze_chat_model_view(_chat_envelope(), _snapshot())

    assert {row["system"] for row in zenith} == {"ZENITH"}
    assert {row["system"] for row in chat} == {"CHAT_MODEL"}
    assert zenith[0]["prediction_family_id"] != chat[0]["prediction_family_id"]


def test_incomplete_zenith_scenario_is_explicitly_non_scorable() -> None:
    state = _decision_state()
    state["scenario_packet"]["scenarios"][0].pop("event_steps")

    frozen = freeze_zenith_decisions(state, _snapshot(), "ANALYSIS_1")

    assert frozen[0]["quality"]["scorable_status"] == "NON_SCORABLE"
    assert "MISSING_EVENT_STEPS" in frozen[0]["non_scorable_reasons"]


def test_missing_horizon_is_recorded_as_unspecified_but_never_scorable() -> None:
    state = _decision_state()
    state["scenario_packet"]["scenarios"][0].pop("horizons")

    frozen = freeze_zenith_decisions(state, _snapshot(), "ANALYSIS_1")

    assert frozen[0]["horizons"] == ["UNSPECIFIED"]
    assert frozen[0]["quality"]["scorable_status"] == "NON_SCORABLE"
    assert "MISSING_HORIZONS" in frozen[0]["non_scorable_reasons"]


def test_measurable_zenith_candidate_freezes_single_target_setup() -> None:
    state = _decision_state()
    state["entry_packet"]["candidates"] = [
        {
            "candidate_id": "CANDIDATE_1", "semantic_candidate_id": "OPPORTUNITY_1",
            "side": "BUY", "entry": 4018.0, "stop": 4014.0,
            "scoring_target": 4026.0, "expiry_time": "2026-07-22T10:00:00+00:00",
            "horizons": ["PT1H"], "timeframe": "M5", "variant_id": "FULL",
        }
    ]

    frozen = freeze_zenith_decisions(state, _snapshot(), "ANALYSIS_1")
    setup = next(row for row in frozen if row["decision_type"] == "SETUP")

    assert setup["decision_subtype"] == "SINGLE_TARGET_SETUP"
    assert setup["semantic_opportunity_id"] == "OPPORTUNITY_1"
    assert setup["setup_geometry"]["scoring_target"] == 4026.0
    assert setup["quality"]["scorable_status"] == "SCORABLE"


def test_chat_model_snapshot_binding_is_required() -> None:
    envelope = _chat_envelope()
    envelope["snapshot_id"] = "OTHER_SNAPSHOT"

    try:
        freeze_chat_model_view(envelope, _snapshot())
    except ValueError as exc:
        assert "snapshot binding" in str(exc)
    else:
        raise AssertionError("mismatched chat snapshot was accepted")


def test_material_revision_gets_new_decision_id_before_start() -> None:
    original = freeze_chat_model_view(_chat_envelope(), _snapshot())[0]
    revised = revise_decision(
        original,
        {"direction": "BEARISH"},
        revision_time=NOW - timedelta(seconds=1),
    )

    assert revised["revision_type"] == "MATERIAL_REVISION"
    assert revised["decision_id"] != original["decision_id"]
    assert revised["original_decision_id"] == original["decision_id"]


def test_late_material_revision_is_audit_only() -> None:
    original = freeze_chat_model_view(_chat_envelope(), _snapshot())[0]
    correction = revise_decision(original, {"direction": "BEARISH"}, revision_time=NOW)

    assert correction["revision_type"] == "AUDIT_ONLY_LATE_CORRECTION"
    assert correction["decision_id"] == original["decision_id"]
    assert original["direction"] == "BULLISH"


def test_record_frozen_decisions_is_valid_and_idempotent(tmp_path: Path) -> None:
    ledger = AppendOnlyLedger(tmp_path / "events.jsonl")
    decisions = freeze_chat_model_view(_chat_envelope(), _snapshot())

    first = record_frozen_decisions(ledger, decisions)
    second = record_frozen_decisions(ledger, decisions)

    assert first == second
    assert len(ledger.read_all()) == len(decisions)
    assert ledger.read_all()[0]["event_type"] == "DECISION_FROZEN"
