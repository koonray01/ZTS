from __future__ import annotations

FAILURE_MODE_DEFINITIONS = {
    "WICK_AS_BREAK": {
        "severity": "HIGH",
        "description": "A wick-through was classified as a confirmed structural break.",
    },
    "OPEN_BAR_CONFIRMATION": {
        "severity": "CRITICAL",
        "description": "An unclosed bar was used as confirmation.",
    },
    "HINDSIGHT_BOUNDARY": {
        "severity": "CRITICAL",
        "description": "A zone or boundary was repaired after future information became known.",
    },
    "SAME_BAR_SL_TP_AMBIGUITY": {
        "severity": "HIGH",
        "description": "Historical bar touched both SL and TP without resolvable order.",
    },
    "MANUAL_OVERRIDE_CREDIT": {
        "severity": "HIGH",
        "description": "A manual override was incorrectly credited to the Entry Engine.",
    },
    "SHOCK_CHASE": {
        "severity": "HIGH",
        "description": "A normal-logic entry chased price during an active shock.",
    },
    "VERSION_MIXING": {
        "severity": "CRITICAL",
        "description": "Evidence or results from different logic versions were mixed.",
    },
    "FUTURE_LEAKAGE_VIOLATION": {
        "severity": "CRITICAL",
        "description": "A replay decision used information unavailable at decision time.",
    },
    "PERMISSION_OVERREACH": {
        "severity": "HIGH",
        "description": "An action exceeded the deterministic permission state.",
    },
    "STOP_WIDENING_ALLOWED": {
        "severity": "HIGH",
        "description": "The management plan allowed widening the stop.",
    },
    "ADD_TO_LOSER_ALLOWED": {
        "severity": "HIGH",
        "description": "The management plan allowed adding to a losing position.",
    },
}


def describe_failure(code: str) -> dict:
    return FAILURE_MODE_DEFINITIONS.get(
        code,
        {
            "severity": "UNKNOWN",
            "description": "Unregistered failure mode.",
        },
    )
