from __future__ import annotations

import json

from ctl_replay_training import summarize_candidate_lifecycle


def test_candidate_lifecycle_tracks_status_transitions(tmp_path):
    for index, status in enumerate(["WAIT", "WAIT", "READY_FOR_PERMISSION_REVIEW"]):
        payload = {
            "snapshot_id": f"S{index}",
            "market_packet": {"generated_at": f"2026-07-13T12:0{index}:00Z"},
            "entry_packet": {"candidates": [{"candidate_id": "C1", "scenario_id": "SC1", "side": "BUY", "entry_type": "EARLY_CONFIRMATION", "status": status}]},
        }
        item_dir = tmp_path / str(index)
        item_dir.mkdir()
        (item_dir / "decision_state.json").write_text(json.dumps({"payload": payload}), encoding="utf-8")
    report = summarize_candidate_lifecycle(tmp_path)
    assert report["snapshots_analyzed"] == 3
    assert report["unique_candidate_count"] == 1
    assert report["status_transition_counts"] == {"WAIT->READY_FOR_PERMISSION_REVIEW": 1}
    assert report["final_status_counts"] == {"READY_FOR_PERMISSION_REVIEW": 1}
