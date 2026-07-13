from __future__ import annotations

from typing import Any


def normalize_outcome(outcome: dict[str, Any], entry_origin: str) -> dict[str, Any]:
    classification = outcome["classification"]
    realized_r = float(outcome.get("realized_r", 0.0))

    if classification == "NO_TRIGGER":
        realized_r = 0.0
    clean_win = classification == "TP_FIRST" and realized_r > 0
    if classification == "AMBIGUOUS_SAME_BAR":
        clean_win = False
    if entry_origin == "MANUAL_OVERRIDE":
        classification = "MANUAL_OVERRIDE"
        clean_win = False

    return {
        "classification": classification,
        "realized_r": realized_r,
        "clean_win": clean_win,
    }


def entry_engine_credit(
    entry_origin: str,
    outcome: dict[str, Any],
    *,
    candidate_valid: bool,
    candidate_ready: bool,
    deterministic_fail: bool,
) -> bool:
    if entry_origin != "SYSTEM_CANDIDATE":
        return False
    if not candidate_valid or not candidate_ready or deterministic_fail:
        return False
    return outcome["classification"] not in {"MANUAL_OVERRIDE"}
