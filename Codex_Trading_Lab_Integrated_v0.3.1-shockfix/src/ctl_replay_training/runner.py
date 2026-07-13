from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .case import ReplayCase
from .episode import build_episode_bundle
from .judge import judge_submission
from .session import ReplaySession
from .submission import FrozenSubmission
from .utils import sha256_json


def verify_hash_chain(chain: list[dict[str, Any]]) -> bool:
    previous = "0" * 64
    for index, link in enumerate(chain):
        if link.get("index") != index or link.get("previous_hash") != previous:
            return False
        payload = {key: value for key, value in link.items() if key != "link_hash"}
        if link.get("link_hash") != sha256_json(payload):
            return False
        previous = link["link_hash"]
    return True


def run_case(
    *,
    case: ReplayCase,
    submission: dict[str, Any],
    created_at: datetime | None = None,
) -> dict[str, Any]:
    session = ReplaySession(case)
    observation = session.observe()
    frozen = session.submit(submission)
    hidden = session.reveal()
    score = judge_submission(
        case_id=case.case_id,
        submission=frozen.value,
        decision_state=session.current_decision_state,
        hidden_outcome=hidden,
        judge_key=case.load_judge_key(),
    )
    episode = build_episode_bundle(
        case_manifest=case.manifest,
        visible_snapshot_id=observation["snapshot"]["snapshot_id"],
        submission=frozen.value,
        visible_packet={
            "market_packet": observation["market_packet"],
            "scenario_packet": observation["scenario_packet"],
            "entry_packet": observation["entry_packet"],
        },
        hidden_outcome=hidden,
        score=score,
        created_at=created_at,
    )
    return {
        "observation": observation,
        "submission": frozen.value,
        "submission_hash": frozen.submission_hash,
        "hidden_outcome": hidden,
        "score": score,
        "episode": episode,
    }


def run_trajectory(
    *,
    case: ReplayCase,
    submissions: list[dict[str, Any]],
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Run one submission per visible step; reveal only after final T3."""
    if len(submissions) != len(case.steps):
        raise ValueError("trajectory requires exactly one submission per visible step")
    session = ReplaySession(case)
    observations: list[dict[str, Any]] = []
    frozen: list[FrozenSubmission] = []
    chain: list[dict[str, Any]] = []
    previous_hash = "0" * 64
    for index, submission in enumerate(submissions):
        observation = session.observe()
        observations.append(observation)
        frozen_submission = session.submit(submission)
        frozen.append(frozen_submission)
        link = {"index": index, "step_id": observation["step_id"], "snapshot_id": observation["snapshot"]["snapshot_id"], "submission_hash": frozen_submission.submission_hash, "previous_hash": previous_hash}
        link["link_hash"] = sha256_json(link)
        chain.append(link)
        previous_hash = link["link_hash"]
        if index < len(submissions) - 1:
            session.advance()
    hidden = session.reveal()
    final = frozen[-1]
    score = judge_submission(
        case_id=case.case_id,
        submission=final.value,
        decision_state=session.current_decision_state,
        hidden_outcome=hidden,
        judge_key=case.load_judge_key(),
    )
    episode = build_episode_bundle(
        case_manifest=case.manifest,
        visible_snapshot_id=observations[-1]["snapshot"]["snapshot_id"],
        submission=final.value,
        visible_packet={
            "market_packet": observations[-1]["market_packet"],
            "scenario_packet": observations[-1]["scenario_packet"],
            "entry_packet": observations[-1]["entry_packet"],
        },
        hidden_outcome=hidden,
        score=score,
        created_at=created_at,
    )
    trajectory_score = {
        "scored_stage": case.steps[-1].get("stage", "SINGLE"),
        "final_score_only": True,
        "intermediate_scores": None,
        "final_score": score["total_score"],
        "entry_engine_credit": score["entry_engine_credit"],
    }
    return {"observations": observations, "submissions": [item.value for item in frozen], "hidden_outcome": hidden, "score": score, "trajectory_score": trajectory_score, "episode": episode, "hash_chain": chain, "trajectory_hash": previous_hash, "hash_chain_valid": verify_hash_chain(chain)}
