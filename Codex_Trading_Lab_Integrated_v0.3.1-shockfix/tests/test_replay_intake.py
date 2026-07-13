from __future__ import annotations

import json

from ctl_replay_training import build_replay_intake


def test_replay_intake_requires_live_source_and_keeps_outcome_unlabeled(tmp_path):
    payload = {
        "snapshot_id": "SNAP_INTAKE_001",
        "market_packet": {
            "symbol": "XAUUSD",
            "generated_at": "2026-07-13T12:00:00Z",
            "data_quality": {"source": "LIVE_MT5", "freshness": "FRESH", "qc_decision": "PASS"},
            "market_state": [],
            "location": {},
            "risk_flags": [],
            "conflicts": [],
        },
        "entry_packet": {"candidates": [{"candidate_id": "C1", "status": "WAIT"}]},
    }
    path = tmp_path / "decision_state.json"
    path.write_text(json.dumps({"payload": payload}), encoding="utf-8")
    report = build_replay_intake(tmp_path)
    assert report["source"] == "LIVE_MT5"
    assert report["summary"]["candidate_count"] == 1
    assert report["summary"]["labeled_outcome_count"] == 0
    assert report["records"][0]["outcome_status"] == "UNLABELED"
