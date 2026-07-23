from __future__ import annotations

import json
import sqlite3

from ctl_analysis_registry.reporting import build_performance_report


def _connection(rows: list[dict]) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE model_outcomes (payload_json TEXT)")
    connection.execute("CREATE TABLE evaluation_jobs (payload_json TEXT)")
    for row in rows:
        connection.execute("INSERT INTO model_outcomes VALUES (?)", (json.dumps(row),))
    return connection


def _setup_outcome(
    *,
    opportunity: str,
    strictness: str,
    classification: str,
    generation: str = "GEN_1",
) -> dict:
    return {
        "outcome_id": f"OUT_{opportunity}_{strictness}",
        "decision_id": f"DEC_{opportunity}_{strictness}",
        "decision_type": "SETUP",
        "classification": classification,
        "system": "CHAT_MODEL",
        "horizon": "PT30M",
        "setup_horizon": "SCALPING",
        "side": "SELL",
        "strictness": strictness,
        "generation_id": generation,
        "prediction_family_id": "FAMILY_XAUUSD",
        "semantic_opportunity_id": opportunity,
        "variant_id": strictness,
        "market_context": {"regime": "BEARISH"},
        "integrity_tier": "VERIFIED",
        "realized_r": 2.0 if classification == "TP_FIRST" else -1.0,
    }


def test_four_strictness_variants_count_as_one_headline_opportunity() -> None:
    rows = [
        _setup_outcome(opportunity="OPP_1", strictness=value, classification="TP_FIRST")
        for value in ("EXPLORATORY", "VERY_RELAXED", "RELAXED", "NORMAL")
    ]

    report = build_performance_report(_connection(rows), {"system": "CHAT_MODEL"})

    assert report["setup"]["raw_variant_count"] == 4
    assert report["setup"]["unique_opportunity_count"] == 1


def test_strictness_cohorts_remain_separate() -> None:
    rows = [
        _setup_outcome(opportunity="OPP_1", strictness="EXPLORATORY", classification="TP_FIRST"),
        _setup_outcome(opportunity="OPP_1", strictness="NORMAL", classification="SL_FIRST"),
    ]

    report = build_performance_report(_connection(rows), {"system": "CHAT_MODEL"})

    assert report["setup"]["strictness_cohorts"]["EXPLORATORY"]["tp_first"] == 1
    assert report["setup"]["strictness_cohorts"]["NORMAL"]["sl_first"] == 1
    assert set(report["setup"]["variant_cohorts"]) == {
        "CHAT_MODEL|SCALPING|EXPLORATORY|SELL|BEARISH",
        "CHAT_MODEL|SCALPING|NORMAL|SELL|BEARISH",
    }


def test_generation_is_part_of_headline_identity() -> None:
    rows = [
        _setup_outcome(
            opportunity="OPP_1", strictness="NORMAL", classification="TP_FIRST", generation="GEN_1"
        ),
        _setup_outcome(
            opportunity="OPP_1", strictness="NORMAL", classification="SL_FIRST", generation="GEN_2"
        ),
    ]

    report = build_performance_report(_connection(rows), {"system": "CHAT_MODEL"})

    assert report["setup"]["unique_opportunity_count"] == 2
