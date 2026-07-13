from __future__ import annotations

import json
from pathlib import Path

from ctl_replay_training.case import ReplayCase
from ctl_replay_training.runner import run_case


ROOT = Path(__file__).resolve().parents[1]


def test_unknown_candidate_cannot_receive_entry_engine_credit():
    case = ReplayCase.load(ROOT / "examples" / "cases" / "bullish_continuation")
    submission = json.loads(
        (ROOT / "examples" / "decisions" / "bullish_continuation.correct.json").read_text(encoding="utf-8")
    )
    submission["selected_scenario_id"] = "SCN_STALE_UNKNOWN"
    submission["selected_candidate_id"] = "ENTRY_STALE_UNKNOWN"
    result = run_case(case=case, submission=submission)
    assert result["score"]["entry_engine_credit"] is False
    assert "UNKNOWN_ENTRY_CANDIDATE" in result["score"]["failure_modes"]
