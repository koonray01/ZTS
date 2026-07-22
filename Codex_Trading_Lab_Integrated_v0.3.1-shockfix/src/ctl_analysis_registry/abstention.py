"""Frozen-control abstention outcome mapping."""

from __future__ import annotations

from typing import Any

from .identity import stable_id


_MAPPING = {
    "SL_FIRST": "PROTECTED_FROM_LOSS",
    "TP_FIRST": "MISSED_WINNER",
    "ENTRY_NOT_TRIGGERED": "CORRECT_PATIENCE",
    "EXPIRED_UNTRIGGERED": "CORRECT_PATIENCE",
    "UNRESOLVED": "NO_MATERIAL_OPPORTUNITY",
}


def label_abstention(
    decision: dict[str, Any],
    control_outcome: dict[str, Any] | None,
) -> dict[str, Any]:
    base = {
        "outcome_id": stable_id("MODEL_OUTCOME", decision["decision_id"], decision["labeling_policy_version"]),
        "decision_id": decision["decision_id"], "decision_type": "ABSTENTION",
        "system": decision["system"], "original_policy_version": decision["labeling_policy_version"],
        "safety": dict(decision.get("safety", {})),
    }
    control = decision.get("frozen_control")
    required = {"entry", "stop", "scoring_target", "expiry_time"}
    if not isinstance(control, dict) or not required <= control.keys():
        return {**base, "classification": "NOT_SCORABLE", "reason_codes": ["FROZEN_CONTROL_MISSING"]}
    if not isinstance(control_outcome, dict):
        return {**base, "classification": "INVALID_INPUT", "reason_codes": ["CONTROL_OUTCOME_MISSING"]}
    control_class = control_outcome.get("classification")
    if decision.get("action") == "WAIT" and control_class == "TP_FIRST":
        classification = "UNNECESSARY_DELAY"
    else:
        classification = _MAPPING.get(str(control_class), "INVALID_INPUT")
    return {
        **base, "classification": classification,
        "control_classification": control_class,
        "reason_codes": [] if classification != "INVALID_INPUT" else ["CONTROL_OUTCOME_UNSUPPORTED"],
    }
