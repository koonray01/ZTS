from __future__ import annotations

from ctl_analysis_registry.backfill import backfill_eligible, classify_legacy_decision


def _event(decision_type="SCENARIO", **payload):
    return {
        "schema_version": "ANALYSIS_REGISTRY_EVENT_V0_1", "event_id": "E1",
        "event_type": "DECISION_RECORDED", "source_class": "LIVE_MT5",
        "decision_time": "2026-07-20T09:00:00Z",
        "payload": {"decision_id": "D1", "decision_type": decision_type, "horizons": ["PT1H"], **payload},
    }


def _bundle(**overrides):
    result = {
        "source_qc": "PASS", "quarantined": False, "frozen_before_outcome": True,
        "evidence_refs": ["SNAP_1"],
    }
    result.update(overrides)
    return result


def test_phase1_scenario_without_machine_readable_criteria_is_non_scorable() -> None:
    assert classify_legacy_decision(_event(), _bundle()) == "NON_SCORABLE_LEGACY"


def test_quarantined_legacy_snapshot_is_invalid_input() -> None:
    event = _event("SETUP", setup_geometry={"entry": 100, "stop": 99, "scoring_target": 102, "expiry_time": "2026-07-20T10:00:00Z"})
    assert classify_legacy_decision(event, _bundle(quarantined=True)) == "INVALID_INPUT"


def test_backfill_never_parses_chat_prose_for_levels(tmp_path) -> None:
    event = _event("DIRECTIONAL", narrative="Gold should rise toward 4100")
    event["source_class"] = "CHAT_ONLY"

    result = backfill_eligible(event, _bundle(future_chart={"target": 4100}), tmp_path / "events.jsonl", dry_run=True)

    assert result["classification"] == "NON_SCORABLE_LEGACY"
    assert result["created_decisions"] == 0


def test_measurable_preoutcome_directional_is_backfill_eligible() -> None:
    event = _event("DIRECTIONAL", direction="BULLISH", reference_price=100.0, atr=1.0)
    assert classify_legacy_decision(event, _bundle()) == "BACKFILL_ELIGIBLE"


def test_missing_source_evidence_is_insufficient() -> None:
    event = _event("DIRECTIONAL", direction="BULLISH", reference_price=100.0, atr=1.0)
    assert classify_legacy_decision(event, _bundle(evidence_refs=[])) == "INSUFFICIENT_EVIDENCE"
