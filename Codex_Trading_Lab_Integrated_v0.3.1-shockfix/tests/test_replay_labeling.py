from __future__ import annotations

from ctl_replay_training import build_outcome_label_queue


def test_label_queue_excludes_wait_candidates_and_never_infers_outcome():
    intake = {
        "source": "LIVE_MT5",
        "symbol": "XAUUSD",
        "partition": "FORWARD_SHADOW",
        "records": [{
            "intake_id": "I1",
            "snapshot_id": "S1",
            "capture_time": "2026-07-13T12:00:00Z",
            "symbol": "XAUUSD",
            "source": "LIVE_MT5",
            "partition": "FORWARD_SHADOW",
            "candidates": [
                {"candidate_id": "WAIT", "status": "WAIT"},
                {"candidate_id": "READY", "status": "READY_FOR_PERMISSION_REVIEW"},
            ],
        }],
    }
    queue = build_outcome_label_queue(intake)
    assert queue["readiness"] == "READY_FOR_LABELING"
    assert queue["summary"]["labelable_candidate_count"] == 1
    assert queue["items"][0]["outcome_classification"] is None
    assert queue["items"][0]["realized_r"] is None


def test_label_queue_reports_empty_when_no_ready_candidate():
    intake = {"source": "LIVE_MT5", "symbol": "XAUUSD", "partition": "FORWARD_SHADOW", "records": []}
    queue = build_outcome_label_queue(intake)
    assert queue["readiness"] == "NO_LABELABLE_CANDIDATES"
