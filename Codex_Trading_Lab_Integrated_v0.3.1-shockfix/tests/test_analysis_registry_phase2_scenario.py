from __future__ import annotations

from ctl_analysis_registry.scenario import label_scenario


def _step(step_id, sequence, event_type, **geometry):
    return {"step_id": step_id, "sequence": sequence, "event_type": event_type, "required": True, **geometry}


def _decision():
    return {
        "decision_id": "SCENARIO_DECISION_1", "system": "ZENITH", "decision_type": "SCENARIO",
        "labeling_policy_version": "ORDERED_SCENARIO_V1",
        "rules": {
            "success": [
                _step("S1", 1, "CLOSED_ABOVE", level=101.0),
                _step("S2", 2, "TOUCHED_BAND", lower=102.0, upper=103.0),
            ],
            "failure": {"event_type": "INVALIDATION_HIT", "level": 99.0},
            "invalidation": {"event_type": "INVALIDATION_HIT", "level": 99.0},
            "expiry": "2026-07-22T11:00:00Z",
        },
        "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0},
    }


def _job():
    return {"job_id": "JOB_SCENARIO_1", "horizon": "PT1H"}


def _evidence(events, *, expired=False, qc="PASS"):
    return {
        "evidence_id": "EVIDENCE_1", "events": events, "expired": expired,
        "qc": {"status": qc, "reasons": []}, "evidence_refs": ["EVIDENCE_1"],
    }


def test_required_scenario_steps_must_complete_in_order() -> None:
    evidence = _evidence([
        {"event_type": "TOUCHED_BAND", "event_time": "2026-07-22T10:05:00Z", "price": 102.5},
        {"event_type": "CLOSED_ABOVE", "event_time": "2026-07-22T10:10:00Z", "price": 101.5},
    ])

    assert label_scenario(_decision(), _job(), evidence)["classification"] == "UNRESOLVED"


def test_required_scenario_steps_confirm_in_order() -> None:
    evidence = _evidence([
        {"event_type": "CLOSED_ABOVE", "event_time": "2026-07-22T10:05:00Z", "price": 101.5},
        {"event_type": "TOUCHED_BAND", "event_time": "2026-07-22T10:10:00Z", "price": 102.5},
    ])

    result = label_scenario(_decision(), _job(), evidence)
    assert result["classification"] == "CONFIRMED"
    assert result["completion_ratio"] == 1.0


def test_provable_invalidation_precedence_wins() -> None:
    evidence = _evidence([
        {"event_type": "INVALIDATION_HIT", "event_time": "2026-07-22T10:01:00Z", "price": 98.9},
        {"event_type": "CLOSED_ABOVE", "event_time": "2026-07-22T10:05:00Z", "price": 101.5},
    ])

    assert label_scenario(_decision(), _job(), evidence)["classification"] == "INVALIDATED"


def test_same_time_completion_and_invalidation_is_unresolved() -> None:
    evidence = _evidence([
        {"event_type": "CLOSED_ABOVE", "event_time": "2026-07-22T10:05:00Z", "price": 101.5},
        {"event_type": "TOUCHED_BAND", "event_time": "2026-07-22T10:10:00Z", "price": 102.5},
        {"event_type": "INVALIDATION_HIT", "event_time": "2026-07-22T10:10:00Z", "price": 98.9},
    ])

    assert label_scenario(_decision(), _job(), evidence)["classification"] == "UNRESOLVED"


def test_expired_partial_path_is_partially_confirmed() -> None:
    evidence = _evidence([
        {"event_type": "CLOSED_ABOVE", "event_time": "2026-07-22T10:05:00Z", "price": 101.5},
    ], expired=True)

    result = label_scenario(_decision(), _job(), evidence)
    assert result["classification"] == "PARTIALLY_CONFIRMED"
    assert result["completion_ratio"] == 0.5
