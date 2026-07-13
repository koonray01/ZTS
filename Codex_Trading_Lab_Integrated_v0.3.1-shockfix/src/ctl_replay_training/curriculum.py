from __future__ import annotations

from collections import Counter
from typing import Any


FAILURE_TO_TAG = {
    "MARKET_READ_DIRECTION_MISMATCH": "market_read",
    "MARKET_READ_PHASE_MISMATCH": "market_phase",
    "MARKET_READ_VOLATILITY_MISMATCH": "volatility",
    "SCENARIO_NOT_SELECTED": "scenario",
    "NON_PREFERRED_SCENARIO": "scenario",
    "PERMISSION_OVERREACH": "permission",
    "PART3_NOT_RESPECTED": "permission",
    "UNNECESSARY_ENTRY_SELECTION": "entry",
    "ENTRY_CANDIDATE_NOT_SELECTED": "entry",
    "NO_INITIAL_STOP": "management",
    "STOP_WIDENING_ALLOWED": "management",
    "ADD_TO_LOSER_ALLOWED": "management",
    "FUTURE_LEAKAGE_VIOLATION": "process",
}


def recommend_next_cases(
    scores: list[dict[str, Any]],
    case_catalog: list[dict[str, Any]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    failure_counts = Counter(
        FAILURE_TO_TAG.get(failure)
        for score in scores
        for failure in score.get("failure_modes", [])
        if FAILURE_TO_TAG.get(failure)
    )
    weakest = [tag for tag, _count in failure_counts.most_common()]
    if not weakest:
        weakest = ["scenario", "permission", "entry"]

    ranked = []
    for case in case_catalog:
        tags = set(case.get("curriculum_tags", []))
        match = sum(1 for tag in weakest if tag in tags)
        ranked.append((match, case["case_id"], case))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:limit]]
