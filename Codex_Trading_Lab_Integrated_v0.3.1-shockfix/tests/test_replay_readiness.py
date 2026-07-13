from __future__ import annotations

import json

from ctl_replay_training import explain_candidate_readiness


def test_readiness_diagnostic_counts_wait_gates(tmp_path):
    payload = {
        "entry_packet": {"candidates": [{
            "candidate_id": "C1",
            "status": "WAIT",
            "side": "BUY",
            "entry_type": "EARLY_CONFIRMATION",
            "trigger": {"status": "PENDING"},
            "missing_conditions": ["RETEST_HOLD"],
            "hard_requirements": [{"requirement_id": "LOCATION", "status": "PENDING"}],
        }]},
        "scenario_packet": {"scenarios": [{
            "status": "ARMED",
            "path": [{"event": "RETEST_HOLD", "state": "PENDING"}],
            "missing_events": ["RETEST_HOLD"],
        }]},
    }
    (tmp_path / "decision_state.json").write_text(json.dumps({"payload": payload}), encoding="utf-8")
    report = explain_candidate_readiness(tmp_path)
    assert report["readiness"] == "NO_READY_CANDIDATE"
    assert report["status_counts"] == {"WAIT": 1}
    assert report["missing_condition_counts"] == {"RETEST_HOLD": 1}
    assert report["location_requirement_counts"] == {"PENDING": 1}
    assert report["scenario_status_counts"] == {"ARMED": 1}
    assert report["scenario_event_state_counts"] == {"RETEST_HOLD=PENDING": 1}
