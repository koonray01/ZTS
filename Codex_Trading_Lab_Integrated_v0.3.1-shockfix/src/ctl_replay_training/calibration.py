from __future__ import annotations

from collections import Counter
from typing import Any


MINIMUM_RESOLVED_SYSTEM_CANDIDATES = 30
MINIMUM_OOS_OR_FORWARD_RESOLVED = 10
MAXIMUM_AMBIGUOUS_RATE_FOR_REVIEW = 0.10

RESOLVED = {"TP_FIRST", "SL_FIRST"}


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else round(numerator / denominator, 6)


def summarize_candidate_quality(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize replay evidence without converting QA into an edge claim.

    Every record must contain a validated ``score`` and ``episode``. Only
    outcomes explicitly credited to ``SYSTEM_CANDIDATE`` by the replay judge
    enter candidate-performance metrics. Process scores remain separate.
    """

    partitions: Counter[str] = Counter()
    classifications: Counter[str] = Counter()
    process_passes = 0
    deterministic_fails = 0
    invalid_reference_episodes = 0
    credited: list[tuple[dict[str, Any], str]] = []

    for record in records:
        score = record["score"]
        episode = record["episode"]
        partition = episode["partition"]
        partitions[partition] += 1
        process_passes += int(bool(score.get("process_pass")))
        deterministic_fails += int(bool(score.get("deterministic_fail")))
        invalid_reference_episodes += int(
            any(
                failure in {"UNKNOWN_SCENARIO_ID", "UNKNOWN_ENTRY_CANDIDATE"}
                for failure in score.get("failure_modes", [])
            )
        )
        if score.get("entry_engine_credit"):
            outcome = score["outcome"]
            credited.append((outcome, partition))
            classifications[outcome["classification"]] += 1

    resolved = [(outcome, partition) for outcome, partition in credited if outcome["classification"] in RESOLVED]
    oos_or_forward_resolved = sum(
        1 for _, partition in resolved if partition in {"LOCKED_OOS", "FORWARD_SHADOW"}
    )
    clean_wins = sum(1 for outcome, _ in resolved if outcome["classification"] == "TP_FIRST" and outcome.get("clean_win"))
    losses = sum(1 for outcome, _ in resolved if outcome["classification"] == "SL_FIRST")
    positive_r = round(sum(max(0.0, float(outcome.get("realized_r", 0.0))) for outcome, _ in resolved), 6)
    negative_r = round(sum(min(0.0, float(outcome.get("realized_r", 0.0))) for outcome, _ in resolved), 6)
    net_r = round(positive_r + negative_r, 6)
    mean_r = None if not resolved else round(net_r / len(resolved), 6)
    profit_factor = None if negative_r == 0 else round(positive_r / abs(negative_r), 6)
    ambiguous_count = classifications["AMBIGUOUS_SAME_BAR"]
    ambiguous_rate = _ratio(ambiguous_count, len(credited))

    estimates_publishable = (
        len(resolved) >= MINIMUM_RESOLVED_SYSTEM_CANDIDATES
        and oos_or_forward_resolved >= MINIMUM_OOS_OR_FORWARD_RESOLVED
    )
    if not estimates_publishable:
        status = "INSUFFICIENT_DATA"
    elif invalid_reference_episodes:
        status = "DATA_QUALITY_BLOCK"
    elif ambiguous_rate is not None and ambiguous_rate > MAXIMUM_AMBIGUOUS_RATE_FOR_REVIEW:
        status = "DATA_QUALITY_BLOCK"
    else:
        status = "READY_FOR_REVIEW"

    return {
        "schema_version": "0.1.0",
        "mode": "RESEARCH_QA_ONLY",
        "calibration_status": status,
        "thresholds": {
            "minimum_resolved_system_candidates": MINIMUM_RESOLVED_SYSTEM_CANDIDATES,
            "minimum_oos_or_forward_resolved": MINIMUM_OOS_OR_FORWARD_RESOLVED,
            "maximum_ambiguous_rate_for_review": MAXIMUM_AMBIGUOUS_RATE_FOR_REVIEW,
        },
        "coverage": {
            "total_episodes": len(records),
            "partition_counts": dict(sorted(partitions.items())),
            "credited_system_candidates": len(credited),
            "resolved_system_candidates": len(resolved),
            "oos_or_forward_resolved": oos_or_forward_resolved,
            "invalid_reference_episodes": invalid_reference_episodes,
        },
        "process_quality": {
            "process_pass_count": process_passes,
            "deterministic_fail_count": deterministic_fails,
            "process_pass_rate": _ratio(process_passes, len(records)),
        },
        "candidate_outcomes": {
            "classification_counts": dict(sorted(classifications.items())),
            "clean_wins": clean_wins,
            "losses": losses,
            "statistical_metrics_suppressed": not estimates_publishable,
            "win_rate_resolved": _ratio(clean_wins, len(resolved)) if estimates_publishable else None,
            "ambiguous_rate": ambiguous_rate,
            "gross_positive_r": positive_r,
            "gross_negative_r": negative_r,
            "net_r": net_r,
            "mean_r_resolved": mean_r if estimates_publishable else None,
            "profit_factor": profit_factor if estimates_publishable else None,
        },
        "trading_edge_established": False,
        "execution_permission_effect": "NONE",
        "limitations": [
            "Replay process scores and candidate outcome metrics are intentionally separate.",
            "READY_FOR_REVIEW is not live-readiness, profitability, or execution permission.",
            "Synthetic outcomes cannot establish trading edge.",
        ],
    }
