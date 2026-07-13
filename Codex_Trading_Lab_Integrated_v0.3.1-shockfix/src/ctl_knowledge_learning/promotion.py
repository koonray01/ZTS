from __future__ import annotations

from typing import Any


def evaluate_promotion(
    *,
    current_stage: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    reasons = []
    blocking = []

    episodes = int(evidence.get("independent_episodes", 0))
    triggered = int(evidence.get("triggered_cases", 0))
    validation = int(evidence.get("validation_cases", 0))
    locked_oos = int(evidence.get("locked_oos_cases", 0))
    integrity_failures = list(evidence.get("integrity_failures", []))
    stream_count = int(evidence.get("stream_count", 1))
    human_approved = bool(evidence.get("human_approved", False))
    tests_passed = bool(evidence.get("tests_passed", False))
    shadow_passed = bool(evidence.get("shadow_passed", False))
    registered_experiment = bool(evidence.get("registered_experiment", False))

    if integrity_failures:
        blocking.append("INTEGRITY_FAILURE:" + ",".join(integrity_failures))
    if stream_count != 1:
        blocking.append("STREAM_MIXING")

    if current_stage == "OBSERVATION":
        target = "HYPOTHESIS"
        if episodes < 3:
            reasons.append("Need at least 3 independent episodes.")
    elif current_stage == "HYPOTHESIS":
        target = "RESEARCH_FINDING"
        if not registered_experiment:
            reasons.append("Registered experiment is required.")
        if triggered < 20:
            reasons.append("Need at least 20 triggered cases.")
    elif current_stage == "RESEARCH_FINDING":
        target = "VALIDATED_FINDING"
        if validation < 50:
            reasons.append("Need at least 50 validation cases.")
        if locked_oos < 1:
            reasons.append("Locked OOS evidence is required.")
    elif current_stage == "VALIDATED_FINDING":
        target = "CANDIDATE_RULE"
        if not tests_passed:
            reasons.append("Tests must pass before candidate rule creation.")
    elif current_stage == "CANDIDATE_RULE":
        target = "APPROVED_POLICY"
        if not human_approved:
            reasons.append("Explicit human approval is required.")
        if not tests_passed:
            reasons.append("Tests must pass.")
        if not shadow_passed:
            reasons.append("Shadow validation must pass.")
    elif current_stage == "APPROVED_POLICY":
        target = "SKILL_UPDATE_PROPOSAL"
        if not human_approved:
            reasons.append("Human approval is required for skill update proposal.")
        if not tests_passed:
            reasons.append("Dependency and regression tests must pass.")
    else:
        raise ValueError(f"Unsupported stage: {current_stage}")

    allowed = not blocking and not reasons
    return {
        "current_stage": current_stage,
        "target_stage": target,
        "allowed": allowed,
        "blocking_reasons": blocking,
        "requirements_missing": reasons,
        "automatic_deployment_allowed": False,
    }
