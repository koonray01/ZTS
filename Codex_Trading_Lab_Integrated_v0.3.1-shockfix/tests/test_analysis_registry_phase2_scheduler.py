from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from ctl_analysis_registry.scheduler import (
    activate_conditional,
    due_jobs,
    parse_duration,
    retry_job,
    schedule_jobs,
)


NOW = "2026-07-22T09:00:00Z"


def _unconditional(*, horizons: list[str] | None = None) -> dict:
    return {
        "decision_id": "DECISION_1",
        "decision_subtype": "UNCONDITIONAL_DIRECTIONAL",
        "decision_time": NOW,
        "evaluation_start": NOW,
        "horizons": horizons or ["PT15M", "PT1H"],
        "labeling_policy_version": "DIRECTIONAL_TERMINAL_ATR_V1",
        "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0},
    }


def _conditional(*, horizon: str = "PT1H", activation_level: float = 4061.0) -> dict:
    return {
        "decision_id": "DECISION_CONDITIONAL_1",
        "decision_subtype": "CONDITIONAL_DIRECTIONAL",
        "decision_time": NOW,
        "horizons": [horizon],
        "labeling_policy_version": "DIRECTIONAL_TERMINAL_ATR_V1",
        "activation": {
            "condition": {
                "event_type": "CLOSED_ABOVE", "timeframe": "M5",
                "price_field": "MID_CLOSE", "level": activation_level,
            },
            "reference_price_method": "ACTIVATION_BAR_CLOSE_MID",
            "atr_config": {"timeframe": "M5", "period": 14, "method": "WILDER"},
            "expiry_time": "2026-07-22T12:00:00Z",
        },
        "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0},
    }


def _bar(*, close_time: str, close: float, atr: float = 3.5, bar_id: str = "BAR_1") -> dict:
    return {
        "bar_id": bar_id, "timeframe": "M5",
        "open_time": "2026-07-22T10:00:00Z", "close_time": close_time,
        "mid_close": close, "atr": atr, "closed": True,
        "source": "LIVE_MT5", "qc": "PASS",
    }


def test_same_decision_horizon_policy_has_stable_job_id() -> None:
    first = schedule_jobs(_unconditional())
    second = schedule_jobs(_unconditional())

    assert [job["job_id"] for job in first] == [job["job_id"] for job in second]
    assert [job["horizon"] for job in first] == ["PT15M", "PT1H"]
    assert first[0]["evaluation_deadline"] == "2026-07-22T09:15:00Z"


def test_conditional_job_waits_for_activation() -> None:
    job = schedule_jobs(_conditional())[0]

    assert job["state"] == "WAITING_ACTIVATION"
    assert job["evaluation_start"] is None
    assert job["due_at"] == "2026-07-22T12:00:00Z"


def test_conditional_job_clock_starts_at_activation_close() -> None:
    activation = activate_conditional(
        _conditional(),
        [_bar(close_time="2026-07-22T10:05:00Z", close=4062.0)],
    )

    assert activation["evaluation_start"] == "2026-07-22T10:05:00Z"
    assert activation["evaluation_deadlines"] == {"PT1H": "2026-07-22T11:05:00Z"}
    assert activation["evaluation_reference_price_method"] == "ACTIVATION_BAR_CLOSE_MID"
    assert activation["evaluation_reference_price"] == 4062.0
    assert activation["evaluation_atr"] == 3.5


def test_open_or_wrong_timeframe_bar_cannot_activate() -> None:
    open_bar = _bar(close_time="2026-07-22T10:05:00Z", close=4062.0)
    open_bar["closed"] = False
    wrong_timeframe = _bar(close_time="2026-07-22T10:10:00Z", close=4063.0)
    wrong_timeframe["timeframe"] = "M15"

    assert activate_conditional(_conditional(), [open_bar, wrong_timeframe]) is None


def test_expired_untriggered_is_terminal_not_negative_outcome() -> None:
    result = activate_conditional(
        _conditional(),
        [_bar(close_time="2026-07-22T12:05:00Z", close=4060.0)],
    )

    assert result["state"] == "EXPIRED_UNTRIGGERED"
    assert result["classification"] is None


def test_duration_parser_rejects_trade_style_words() -> None:
    assert parse_duration("P1D").total_seconds() == 86400
    with pytest.raises(ValueError, match="ISO-8601"):
        parse_duration("SCALPING")


def test_due_jobs_are_bounded_and_sorted_by_deadline_then_id() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE evaluation_jobs (job_id TEXT, state TEXT, due_at TEXT, payload_json TEXT)"
    )
    for job_id, due_at in (("JOB_B", "2026-07-22T09:10:00Z"), ("JOB_A", "2026-07-22T09:10:00Z"), ("JOB_C", "2026-07-22T10:00:00Z")):
        payload = {"job_id": job_id, "state": "PENDING", "due_at": due_at}
        connection.execute(
            "INSERT INTO evaluation_jobs VALUES (?, ?, ?, ?)",
            (job_id, "PENDING", due_at, json.dumps(payload)),
        )
    connection.commit()

    result = due_jobs(connection, datetime(2026, 7, 22, 9, 30, tzinfo=timezone.utc), limit=1)

    assert [job["job_id"] for job in result] == ["JOB_A"]


def test_history_retries_never_become_negative_outcomes() -> None:
    job = schedule_jobs(_unconditional(horizons=["PT15M"]))[0]

    retrying = retry_job(job, "MT5_HISTORY_UNAVAILABLE", max_attempts=2)
    exhausted = retry_job(retrying, "MT5_HISTORY_UNAVAILABLE", max_attempts=2)

    assert retrying["state"] == "RETRY_PENDING"
    assert exhausted["state"] == "INSUFFICIENT_EVIDENCE"
    assert exhausted["terminal_reason"] == "HISTORY_RETRY_EXHAUSTED"
    assert "classification" not in exhausted
