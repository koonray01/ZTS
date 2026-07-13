from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctl_replay_training.case import ReplayCase
from ctl_replay_training.session import ReplayIdentityError, ReplaySession, OutcomeNotRevealed
from ctl_replay_training.submission import FrozenSubmission
from ctl_replay_training.runner import run_trajectory
from ctl_replay_training.runner import verify_hash_chain


ROOT = Path(__file__).resolve().parents[1]


def _decision() -> dict:
    return json.loads((ROOT / "examples" / "decisions" / "bullish_continuation.correct.json").read_text(encoding="utf-8"))


def test_frozen_submission_is_deeply_immutable():
    original = {"nested": {"value": 1}}
    frozen = FrozenSubmission(original)
    original["nested"]["value"] = 2
    returned = frozen.value
    returned["nested"]["value"] = 3
    assert frozen.value["nested"]["value"] == 1


def test_replay_submission_identity_is_bound_to_current_context():
    case = ReplayCase.load(ROOT / "examples" / "cases" / "bullish_continuation")
    session = ReplaySession(case)
    observation = session.observe()
    submission = _decision()
    submission["case_id"] = "CASE-WRONG"
    submission["snapshot_id"] = observation["snapshot"]["snapshot_id"]
    with pytest.raises(ReplayIdentityError):
        session.submit(submission)


def test_multi_stage_reveal_requires_final_t3(tmp_path):
    source_case = ROOT / "examples" / "cases" / "bullish_continuation"
    manifest = json.loads((source_case / "case.json").read_text(encoding="utf-8"))
    manifest["visible_steps"] = [
        {"step_id": "STEP-T0", "stage": "T0", "snapshot_path": "visible/step_001.snapshot.json", "replay_time": "2025-03-03T01:40:00Z"},
        {"step_id": "STEP-T3", "stage": "T3", "snapshot_path": "visible/step_001.snapshot.json", "replay_time": "2025-03-03T01:40:00Z"},
    ]
    (tmp_path / "case.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "visible").mkdir()
    (tmp_path / "visible" / "step_001.snapshot.json").write_text(
        (source_case / "visible" / "step_001.snapshot.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "hidden").mkdir()
    (tmp_path / "hidden" / "outcome.json").write_text((source_case / "hidden" / "outcome.json").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "hidden" / "judge_key.json").write_text((source_case / "hidden" / "judge_key.json").read_text(encoding="utf-8"), encoding="utf-8")
    case = ReplayCase.load(tmp_path)
    session = ReplaySession(case)
    observation = session.observe()
    submission = _decision()
    submission.update({"case_id": case.case_id, "step_id": "STEP-T0", "snapshot_id": observation["snapshot"]["snapshot_id"]})
    session.submit(submission)
    with pytest.raises(OutcomeNotRevealed):
        session.reveal()


def test_multistep_case_manifest_requires_ordered_t3(tmp_path):
    manifest = {
        "case_id": "CASE-ORDER",
        "visible_steps": [
            {"step_id": "S1", "snapshot_path": "s1.json", "replay_time": "2025-01-02T00:00:00Z", "stage": "T0"},
            {"step_id": "S2", "snapshot_path": "s2.json", "replay_time": "2025-01-01T00:00:00Z", "stage": "T3"},
        ],
    }
    (tmp_path / "case.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="monotonically"):
        ReplayCase.load(tmp_path)


def test_hash_chain_detects_tampering():
    chain = [{"index": 0, "step_id": "S1", "snapshot_id": "P1", "submission_hash": "a" * 64, "previous_hash": "0" * 64}]
    from ctl_replay_training.utils import sha256_json
    chain[0]["link_hash"] = sha256_json(chain[0])
    assert verify_hash_chain(chain)
    chain[0]["snapshot_id"] = "P2"
    assert not verify_hash_chain(chain)
