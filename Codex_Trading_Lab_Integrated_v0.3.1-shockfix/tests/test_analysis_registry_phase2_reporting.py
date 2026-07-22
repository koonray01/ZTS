from __future__ import annotations

import json
import sqlite3

from ctl_analysis_registry.reporting import (
    build_coverage_report,
    build_performance_report,
    wilson_interval,
)


def _connection(outcomes=None, jobs=None):
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE model_outcomes (payload_json TEXT)")
    connection.execute("CREATE TABLE evaluation_jobs (payload_json TEXT)")
    for row in outcomes or []:
        connection.execute("INSERT INTO model_outcomes VALUES (?)", (json.dumps(row),))
    for row in jobs or []:
        connection.execute("INSERT INTO evaluation_jobs VALUES (?)", (json.dumps(row),))
    connection.commit()
    return connection


def _outcome(decision_type, classification, *, system="ZENITH", horizon="PT1H", decision_id="D1", **extra):
    return {
        "outcome_id": f"O_{decision_id}", "decision_id": decision_id,
        "decision_type": decision_type, "classification": classification,
        "system": system, "horizon": horizon, "integrity_tier": "VERIFIED",
        **extra,
    }


def _setup(opportunity, variant, classification, index=0):
    return _outcome(
        "SETUP", classification, decision_id=f"{opportunity}_{variant}_{index}",
        semantic_opportunity_id=opportunity, variant_id=variant,
        realized_r=2.0 if classification == "TP_FIRST" else -1.0,
    )


def test_setup_headline_deduplicates_variants_by_semantic_opportunity() -> None:
    rows = [_setup("OPP_1", "EARLY", "TP_FIRST"), _setup("OPP_1", "FULL", "TP_FIRST")]

    report = build_performance_report(_connection(rows), {"system": "ZENITH"})

    assert report["setup"]["raw_variant_count"] == 2
    assert report["setup"]["unique_opportunity_count"] == 1
    assert report["setup"]["representatives"][0]["variant_id"] == "FULL"


def test_horizons_and_systems_never_share_denominator() -> None:
    rows = [
        _outcome("DIRECTIONAL", "CORRECT", system="ZENITH", horizon="PT15M", decision_id="D1"),
        _outcome("DIRECTIONAL", "INCORRECT", system="ZENITH", horizon="PT1H", decision_id="D2"),
        _outcome("DIRECTIONAL", "CORRECT", system="CHAT_MODEL", horizon="PT1H", decision_id="D3"),
    ]

    report = build_performance_report(_connection(rows), {})

    assert set(report["directional"]["cohorts"]) == {"ZENITH|PT15M", "ZENITH|PT1H", "CHAT_MODEL|PT1H"}


def test_expectancy_is_not_headline_before_thirty_triggered_setups() -> None:
    rows = [_setup(f"OPP_{index}", "FULL", "TP_FIRST", index) for index in range(29)]

    report = build_performance_report(_connection(rows), {"system": "ZENITH"})

    assert report["setup"]["headline_status"] == "INSUFFICIENT_EVIDENCE"


def test_expectancy_unlocks_at_thirty_unique_triggered_setups() -> None:
    rows = [_setup(f"OPP_{index}", "FULL", "TP_FIRST" if index < 20 else "SL_FIRST", index) for index in range(30)]
    report = build_performance_report(_connection(rows), {})
    assert report["setup"]["headline_status"] == "DESCRIPTIVE_ONLY"
    assert report["setup"]["triggered_count"] == 30
    assert report["setup"]["expectancy_r"] == 1.0


def test_coverage_categories_reconcile_exactly_to_jobs() -> None:
    jobs = [
        {"job_id": "J1", "state": "PENDING", "system": "ZENITH", "decision_type": "DIRECTIONAL", "horizon": "PT1H"},
        {"job_id": "J2", "state": "LABELED", "system": "ZENITH", "decision_type": "DIRECTIONAL", "horizon": "PT1H"},
        {"job_id": "J3", "state": "INSUFFICIENT_EVIDENCE", "system": "CHAT_MODEL", "decision_type": "DIRECTIONAL", "horizon": "PT1H"},
    ]
    outcomes = [_outcome("DIRECTIONAL", "CORRECT", decision_id="D2", job_id="J2")]

    report = build_coverage_report(_connection(outcomes, jobs), {})

    assert report["total_jobs"] == 3
    assert report["categories"] == {"pending": 1, "resolved": 1, "insufficient": 1}
    assert sum(report["categories"].values()) == report["total_jobs"]


def test_wilson_interval_is_bounded_and_contains_rate() -> None:
    lower, upper = wilson_interval(7, 10)
    assert 0.0 <= lower <= 0.7 <= upper <= 1.0
