"""Deterministic coverage and descriptive performance reporting."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from typing import Any


def wilson_interval(
    successes: int,
    total: int,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("Wilson counts are invalid")
    if total == 0:
        return (0.0, 0.0)
    rate = successes / total
    denominator = 1.0 + z * z / total
    center = (rate + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(rate * (1.0 - rate) / total + z * z / (4.0 * total * total)) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [json.loads(row[0]) for row in connection.execute(f"SELECT payload_json FROM {table}")]


def _matches(row: dict[str, Any], cohort_filter: dict[str, Any]) -> bool:
    return all(row.get(key) == value for key, value in cohort_filter.items() if value is not None)


def build_coverage_report(
    connection: sqlite3.Connection,
    cohort_filter: dict[str, Any],
) -> dict[str, Any]:
    jobs = [row for row in _rows(connection, "evaluation_jobs") if _matches(row, cohort_filter)]
    outcomes = [row for row in _rows(connection, "model_outcomes") if _matches(row, cohort_filter)]
    outcomes_by_job = {row.get("job_id"): row for row in outcomes if row.get("job_id")}
    counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    for job in jobs:
        outcome = outcomes_by_job.get(job.get("job_id"))
        state = str(job.get("state") or "UNKNOWN")
        if state in {"PENDING", "DUE", "WAITING_ACTIVATION", "RETRY_PENDING", "EVIDENCE_COLLECTED"}:
            category = "pending"
        elif state in {"INSUFFICIENT_EVIDENCE", "UNRESOLVABLE"}:
            category = "insufficient"
        elif state == "INVALID_INPUT":
            category = "invalid_input"
        elif outcome is None:
            category = "pending"
        elif outcome.get("integrity_tier", "VERIFIED") != "VERIFIED":
            category = "excluded"
        elif outcome.get("classification") in {"AMBIGUOUS", "AMBIGUOUS_SAME_BAR", "UNRESOLVED"}:
            category = "ambiguous"
        elif outcome.get("classification") in {"NOT_SCORABLE", "NON_SCORABLE"}:
            category = "non_scorable"
        elif outcome.get("classification") == "INVALID_INPUT":
            category = "invalid_input"
        elif outcome.get("classification") == "INSUFFICIENT_FOLLOWUP":
            category = "insufficient"
        else:
            category = "resolved"
        counts[category] += 1
        for reason in job.get("reason_codes", []) or (outcome or {}).get("reason_codes", []):
            reason_counts[str(reason)] += 1
    order = ("pending", "resolved", "invalid_input", "insufficient", "ambiguous", "non_scorable", "excluded")
    categories = {name: counts[name] for name in order if counts[name]}
    if sum(categories.values()) != len(jobs):
        raise RuntimeError("coverage categories do not reconcile to jobs")
    return {
        "schema_version": "ANALYSIS_COVERAGE_REPORT_V0_1",
        "total_jobs": len(jobs), "categories": categories,
        "qc_reason_counts": dict(sorted(reason_counts.items())),
        "cohort_filter": dict(cohort_filter),
        "reconciled": True,
        "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0},
    }


def _classification_cohorts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[f"{row.get('system')}|{row.get('horizon')}"] .append(row)
    result = {}
    for cohort, items in sorted(grouped.items()):
        classifications = Counter(str(item.get("classification")) for item in items)
        total = len(items)
        result[cohort] = {
            "denominator": total,
            "classifications": dict(sorted(classifications.items())),
            "one_vs_rest": {
                label: {
                    "numerator": count, "denominator": total,
                    "rate": count / total if total else None,
                    "wilson_95": wilson_interval(count, total),
                }
                for label, count in sorted(classifications.items())
            },
        }
    return result


def _setup_count_cohorts(
    rows: list[dict[str, Any]],
    key_builder: Any,
) -> dict[str, dict[str, int]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[key_builder(row)][str(row.get("classification") or "UNKNOWN").lower()] += 1
    return {key: dict(sorted(counts.items())) for key, counts in sorted(grouped.items())}


def build_performance_report(
    connection: sqlite3.Connection,
    cohort_filter: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        row for row in _rows(connection, "model_outcomes")
        if _matches(row, cohort_filter) and row.get("integrity_tier", "VERIFIED") == "VERIFIED"
    ]
    directional_rows = [row for row in rows if row.get("decision_type") == "DIRECTIONAL"]
    directional_cohorts = {}
    for cohort, items in sorted(
        ((key, list(group)) for key, group in _group_by_cohort(directional_rows).items())
    ):
        eligible = [item for item in items if item.get("classification") in {"CORRECT", "INCORRECT", "NEUTRAL"}]
        correct = sum(item.get("classification") == "CORRECT" for item in eligible)
        directional_cohorts[cohort] = {
            "numerator": correct, "denominator": len(eligible),
            "correct_rate": correct / len(eligible) if eligible else None,
            "wilson_95": wilson_interval(correct, len(eligible)),
            "unresolved_or_excluded": len(items) - len(eligible),
            "classifications": dict(sorted(Counter(str(item.get("classification")) for item in items).items())),
        }
    setup_rows = [row for row in rows if row.get("decision_type") == "SETUP"]
    grouped_setup: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in setup_rows:
        grouped_setup[(
            str(row.get("prediction_family_id") or row.get("system") or ""),
            str(row.get("semantic_opportunity_id") or row.get("decision_id") or ""),
            str(row.get("generation_id") or ""),
        )].append(row)
    priority = {
        "FULL": 0,
        "NORMAL": 0,
        "CONTINUATION": 1,
        "RELAXED": 1,
        "EARLY": 2,
        "VERY_RELAXED": 2,
        "EXPLORATORY": 3,
    }
    representatives = [
        min(items, key=lambda item: (priority.get(str(item.get("variant_id")), 99), str(item.get("variant_id") or ""), str(item.get("decision_id") or "")))
        for _, items in sorted(grouped_setup.items())
    ]
    triggered = [row for row in representatives if row.get("classification") in {"TP_FIRST", "SL_FIRST"}]
    realized = [float(row["realized_r"]) for row in triggered if isinstance(row.get("realized_r"), (int, float))]
    setup = {
        "raw_variant_count": len(setup_rows),
        "unique_opportunity_count": len(representatives),
        "triggered_count": len(triggered),
        "headline_status": "DESCRIPTIVE_ONLY" if len(triggered) >= 30 else "INSUFFICIENT_EVIDENCE",
        "expectancy_r": round(sum(realized) / len(realized), 6) if len(triggered) >= 30 and realized else None,
        "representatives": representatives,
        "cohorts": _classification_cohorts(representatives),
        "strictness_cohorts": _setup_count_cohorts(
            setup_rows, lambda row: str(row.get("strictness") or row.get("variant_id") or "UNSPECIFIED")
        ),
        "variant_cohorts": _setup_count_cohorts(
            setup_rows,
            lambda row: "|".join((
                str(row.get("system") or ""),
                str(row.get("setup_horizon") or row.get("horizon") or ""),
                str(row.get("strictness") or row.get("variant_id") or "UNSPECIFIED"),
                str(row.get("side") or ""),
                str((row.get("market_context") or {}).get("regime") or "UNKNOWN"),
            )),
        ),
    }
    return {
        "schema_version": "ANALYSIS_PERFORMANCE_REPORT_V0_1",
        "cohort_filter": dict(cohort_filter),
        "directional": {"cohorts": directional_cohorts},
        "scenario": {"cohorts": _classification_cohorts([row for row in rows if row.get("decision_type") == "SCENARIO"])},
        "setup": setup,
        "abstention": {"cohorts": _classification_cohorts([row for row in rows if row.get("decision_type") == "ABSTENTION"])},
        "claims": {"validated_edge": False, "promotion_gate_open": False, "policy_tuned": False},
        "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0},
    }


def _group_by_cohort(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[f"{row.get('system')}|{row.get('horizon')}"] .append(row)
    return grouped
