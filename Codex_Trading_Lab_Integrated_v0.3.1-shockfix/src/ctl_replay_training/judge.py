from __future__ import annotations

from typing import Any

from .outcomes import entry_engine_credit, normalize_outcome
from .utils import sanitize_id
from .visibility import allowed_evidence_refs, detect_future_reference


def _expected_market_read(judge_key: dict[str, Any]) -> dict[str, str]:
    return judge_key["expected_market_read"]


def _score_market_read(submission: dict[str, Any], judge_key: dict[str, Any]) -> tuple[float, list[str]]:
    expected = _expected_market_read(judge_key)
    actual = submission["market_read"]
    score = 0.0
    failures = []
    for field, points in [("direction", 8), ("phase", 6), ("volatility", 6)]:
        if actual[field] == expected[field]:
            score += points
        else:
            failures.append(f"MARKET_READ_{field.upper()}_MISMATCH")
    return score, failures


def _score_scenario(
    submission: dict[str, Any],
    decision_state: dict[str, Any],
    judge_key: dict[str, Any],
) -> tuple[float, list[str]]:
    selected = submission["selected_scenario_id"]
    valid_ids = {item["scenario_id"] for item in decision_state["scenario_packet"]["scenarios"]}
    if selected is None:
        return (20.0, []) if judge_key["expected_action"] in {"NO_TRADE", "WAIT"} else (0.0, ["SCENARIO_NOT_SELECTED"])
    if selected not in valid_ids:
        return 0.0, ["UNKNOWN_SCENARIO_ID"]
    expected = judge_key.get("preferred_scenario_ids", [])
    if selected in expected:
        return 20.0, []
    return 10.0, ["NON_PREFERRED_SCENARIO"]


def _score_permission(
    submission: dict[str, Any],
    judge_key: dict[str, Any],
) -> tuple[float, list[str], bool]:
    action = submission["action"]
    claim = submission["permission_claim"]
    expected = judge_key["expected_action"]
    deterministic_fail = False
    failures = []

    if action == "MANUAL_OVERRIDE":
        failures.append("MANUAL_OVERRIDE_BEFORE_PERMISSION")
        deterministic_fail = True
        return 0.0, failures, deterministic_fail

    if expected in {"NO_TRADE", "WAIT"}:
        if action in {"NO_TRADE", "WAIT"} and claim in {"NOT_EVALUATED", "WAIT", "REJECTED", "INVALIDATED"}:
            return 15.0, [], False
        failures.append("PERMISSION_OVERREACH")
        deterministic_fail = True
        return 0.0, failures, deterministic_fail

    if expected == "REQUEST_PART3":
        if action == "REQUEST_PART3" and claim == "NOT_EVALUATED":
            return 15.0, [], False
        failures.append("PART3_NOT_RESPECTED")
        return 0.0, failures, True

    return 0.0, ["UNKNOWN_EXPECTED_PERMISSION_PATH"], True


def _score_entry(
    submission: dict[str, Any],
    decision_state: dict[str, Any],
    judge_key: dict[str, Any],
) -> tuple[float, list[str]]:
    action = submission["action"]
    selected = submission["selected_candidate_id"]
    valid_candidates = {
        item["candidate_id"]: item for item in decision_state["entry_packet"]["candidates"]
    }
    expected = judge_key["expected_action"]

    if expected in {"NO_TRADE", "WAIT"}:
        if action in {"NO_TRADE", "WAIT"} and selected is None:
            return 20.0, []
        return 0.0, ["UNNECESSARY_ENTRY_SELECTION"]

    if selected is None:
        return 0.0, ["ENTRY_CANDIDATE_NOT_SELECTED"]
    if selected not in valid_candidates:
        return 0.0, ["UNKNOWN_ENTRY_CANDIDATE"]
    if valid_candidates[selected].get("status") != "READY_FOR_PERMISSION_REVIEW":
        return 0.0, ["ENTRY_CANDIDATE_NOT_READY"]
    preferred_types = set(judge_key.get("preferred_entry_types", []))
    if valid_candidates[selected]["entry_type"] in preferred_types:
        return 20.0, []
    return 10.0, ["NON_PREFERRED_ENTRY_TYPE"]


def _score_management(submission: dict[str, Any]) -> tuple[float, list[str]]:
    plan = submission["management_plan"]
    score = 0.0
    failures = []
    if plan["initial_stop_defined"]:
        score += 5
    else:
        failures.append("NO_INITIAL_STOP")
    if plan["target_defined"]:
        score += 4
    else:
        failures.append("NO_TARGET")
    if not plan["widen_stop_allowed"]:
        score += 3
    else:
        failures.append("STOP_WIDENING_ALLOWED")
    if not plan["add_to_loser_allowed"]:
        score += 3
    else:
        failures.append("ADD_TO_LOSER_ALLOWED")
    return score, failures


def _score_process(
    submission: dict[str, Any],
    decision_state: dict[str, Any],
) -> tuple[float, list[str], bool]:
    failures = []
    score = 10.0
    deterministic_fail = False

    future_refs = detect_future_reference(
        submission["evidence_refs"],
        allowed_evidence_refs(decision_state),
    )
    if future_refs:
        failures.append("FUTURE_LEAKAGE_VIOLATION")
        score = 0.0
        deterministic_fail = True

    if submission["entry_origin"] == "MANUAL_OVERRIDE":
        failures.append("MANUAL_OVERRIDE_NO_ENTRY_ENGINE_CREDIT")
        score = max(0.0, score - 5.0)

    if submission["action"] == "REQUEST_PART3" and submission["permission_claim"] == "APPROVED":
        failures.append("FABRICATED_PERMISSION")
        score = 0.0
        deterministic_fail = True

    return score, failures, deterministic_fail


def judge_submission(
    *,
    case_id: str,
    submission: dict[str, Any],
    decision_state: dict[str, Any],
    hidden_outcome: dict[str, Any],
    judge_key: dict[str, Any],
) -> dict[str, Any]:
    market_score, market_failures = _score_market_read(submission, judge_key)
    scenario_score, scenario_failures = _score_scenario(submission, decision_state, judge_key)
    permission_score, permission_failures, permission_fail = _score_permission(submission, judge_key)
    entry_score, entry_failures = _score_entry(submission, decision_state, judge_key)
    management_score, management_failures = _score_management(submission)
    process_score, process_failures, process_fail = _score_process(submission, decision_state)

    normalized_outcome = normalize_outcome(hidden_outcome, submission["entry_origin"])
    failures = (
        market_failures
        + scenario_failures
        + permission_failures
        + entry_failures
        + management_failures
        + process_failures
    )
    ledgers = {
        "market_read": market_score,
        "scenario": scenario_score,
        "permission": permission_score,
        "entry": entry_score,
        "management": management_score,
        "process": process_score,
    }
    total = sum(ledgers.values())
    deterministic_fail = permission_fail or process_fail
    selected = submission.get("selected_candidate_id")
    selected_candidate = next(
        (item for item in decision_state["entry_packet"]["candidates"] if item["candidate_id"] == selected),
        None,
    )
    candidate_valid = selected_candidate is not None
    candidate_ready = bool(
        selected_candidate
        and selected_candidate.get("status") == "READY_FOR_PERMISSION_REVIEW"
        and submission.get("action") == "REQUEST_PART3"
    )

    return {
        "schema_version": "0.1.0",
        "score_id": sanitize_id(f"SCORE_{case_id}_{submission['submission_id']}"),
        "case_id": case_id,
        "submission_id": submission["submission_id"],
        "total_score": total,
        "ledgers": ledgers,
        "outcome": normalized_outcome,
        "failure_modes": list(dict.fromkeys(failures)),
        "deterministic_fail": deterministic_fail,
        "entry_engine_credit": entry_engine_credit(
            submission["entry_origin"],
            normalized_outcome,
            candidate_valid=candidate_valid,
            candidate_ready=candidate_ready,
            deterministic_fail=deterministic_fail,
        ),
        "process_pass": process_score >= 8 and not deterministic_fail,
    }
