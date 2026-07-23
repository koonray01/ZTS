"""Restart-stable evaluation scheduling and closed-bar activation."""

from __future__ import annotations

import json
import re
import sqlite3
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from .identity import stable_id


_DURATION = re.compile(r"^(?:PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?|P(?P<days>\d+)D)$")
CONDITIONAL_SUBTYPES = {"CONDITIONAL_DIRECTIONAL", "CONDITIONAL_SETUP"}


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_duration(value: str) -> timedelta:
    match = _DURATION.fullmatch(value)
    if match is None:
        raise ValueError(f"horizon must be an explicit ISO-8601 duration: {value}")
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    duration = timedelta(days=days, hours=hours, minutes=minutes)
    if duration <= timedelta(0):
        raise ValueError("ISO-8601 duration must be positive")
    return duration


def schedule_jobs(decision: dict[str, Any]) -> list[dict[str, Any]]:
    decision_id = str(decision["decision_id"])
    policy = str(decision["labeling_policy_version"])
    conditional = decision.get("decision_subtype") in CONDITIONAL_SUBTYPES
    if conditional:
        activation = decision.get("activation")
        if not isinstance(activation, dict) or not activation.get("expiry_time"):
            raise ValueError("conditional decision requires activation expiry_time")
        evaluation_start = None
        due_at = str(activation["expiry_time"])
        state = "WAITING_ACTIVATION"
    else:
        evaluation_start = str(decision.get("evaluation_start") or decision["decision_time"])
        state = "PENDING"
    jobs: list[dict[str, Any]] = []
    for horizon in decision.get("horizons", []):
        horizon = str(horizon)
        duration = parse_duration(horizon)
        deadline = None if evaluation_start is None else _iso(_parse_time(evaluation_start) + duration)
        if not conditional:
            due_at = deadline
        jobs.append(
            {
                "job_id": stable_id("EVALUATION_JOB", decision_id, horizon, policy),
                "decision_id": decision_id,
                "horizon": horizon,
                "labeling_policy_version": policy,
                "state": state,
                "due_at": due_at,
                "evaluation_start": evaluation_start,
                "evaluation_deadline": deadline,
                "attempt_count": 0,
                "terminal_reason": None,
                "safety": deepcopy(decision.get("safety", {})),
            }
        )
    return jobs


def _condition_matches(condition: dict[str, Any], bar: dict[str, Any]) -> bool:
    field = str(condition.get("price_field") or "MID_CLOSE").lower()
    price = bar.get(field)
    if price is None and field == "mid_close":
        price = bar.get("close")
    if not isinstance(price, (int, float)):
        return False
    level = condition.get("level")
    if not isinstance(level, (int, float)):
        return False
    event_type = condition.get("event_type")
    if event_type == "CLOSED_ABOVE":
        return price > level
    if event_type == "CLOSED_BELOW":
        return price < level
    if event_type in {"TOUCHED_BAND", "ENTERED_BAND"}:
        lower, upper = condition.get("lower"), condition.get("upper")
        return isinstance(lower, (int, float)) and isinstance(upper, (int, float)) and lower <= price <= upper
    return False


def activate_conditional(
    decision: dict[str, Any],
    closed_bars: list[dict[str, Any]],
) -> dict[str, Any] | None:
    activation = decision.get("activation")
    if not isinstance(activation, dict):
        raise ValueError("decision has no frozen activation contract")
    condition = activation.get("condition")
    if not isinstance(condition, dict):
        raise ValueError("activation condition is required")
    decision_time = _parse_time(str(decision["decision_time"]))
    expiry = _parse_time(str(activation["expiry_time"]))
    observed_after_expiry = False
    for bar in sorted(closed_bars, key=lambda item: str(item.get("close_time") or "")):
        if bar.get("closed") is not True or bar.get("qc") != "PASS" or bar.get("source") != "LIVE_MT5":
            continue
        if bar.get("timeframe") != condition.get("timeframe"):
            continue
        close_time_value = bar.get("close_time")
        if not isinstance(close_time_value, str):
            continue
        close_time = _parse_time(close_time_value)
        if close_time <= decision_time:
            continue
        if close_time > expiry:
            observed_after_expiry = True
            continue
        if not _condition_matches(condition, bar):
            continue
        reference = bar.get("mid_close", bar.get("close"))
        atr = bar.get("atr")
        if not isinstance(reference, (int, float)) or not isinstance(atr, (int, float)) or atr <= 0:
            return {
                "decision_id": decision["decision_id"], "state": "INVALID_INPUT",
                "terminal_reason": "ACTIVATION_REFERENCE_OR_ATR_INVALID", "classification": None,
            }
        deadlines = {
            str(horizon): _iso(close_time + parse_duration(str(horizon)))
            for horizon in decision.get("horizons", [])
        }
        result = {
            "activation_id": stable_id("DECISION_ACTIVATION", decision["decision_id"], bar.get("bar_id"), _iso(close_time)),
            "decision_id": decision["decision_id"], "state": "ACTIVATED",
            "evaluation_start": _iso(close_time), "evaluation_deadlines": deadlines,
            "evaluation_reference_price_method": activation["reference_price_method"],
            "evaluation_reference_price": float(reference), "evaluation_atr": float(atr),
            "atr_config": deepcopy(activation["atr_config"]),
            "activation_bar_id": bar.get("bar_id"), "activation_bar_close_time": _iso(close_time),
            "source": "LIVE_MT5", "classification": None,
            "safety": deepcopy(decision.get("safety", {})),
        }
        if decision.get("decision_subtype") == "CONDITIONAL_SETUP":
            for field in (
                "setup_geometry",
                "strictness",
                "generation_id",
                "semantic_opportunity_id",
            ):
                result[field] = deepcopy(decision.get(field))
        return result
    if observed_after_expiry:
        return {
            "decision_id": decision["decision_id"], "state": "EXPIRED_UNTRIGGERED",
            "terminal_reason": "ACTIVATION_EXPIRY_PASSED", "classification": None,
            "safety": deepcopy(decision.get("safety", {})),
        }
    return None


def due_jobs(
    connection: sqlite3.Connection,
    now: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    if limit < 0:
        raise ValueError("limit cannot be negative")
    if limit == 0:
        return []
    rows = connection.execute(
        """SELECT payload_json FROM evaluation_jobs
        WHERE state IN ('PENDING', 'DUE', 'RETRY_PENDING') AND due_at <= ?
        ORDER BY due_at, job_id LIMIT ?""",
        (_iso(now), limit),
    ).fetchall()
    return [json.loads(row[0]) for row in rows]


def waiting_activation_jobs(
    connection: sqlite3.Connection,
    limit: int,
) -> list[dict[str, Any]]:
    if limit < 0:
        raise ValueError("limit cannot be negative")
    if limit == 0:
        return []
    rows = connection.execute(
        """SELECT payload_json FROM evaluation_jobs
        WHERE state='WAITING_ACTIVATION'
        ORDER BY due_at, job_id LIMIT ?""",
        (limit,),
    ).fetchall()
    return [json.loads(row[0]) for row in rows]


def retry_job(job: dict[str, Any], error: str, *, max_attempts: int) -> dict[str, Any]:
    updated = deepcopy(job)
    updated["attempt_count"] = int(job.get("attempt_count", 0)) + 1
    updated["last_error"] = error
    if updated["attempt_count"] >= max_attempts:
        updated["state"] = "INSUFFICIENT_EVIDENCE"
        updated["terminal_reason"] = "HISTORY_RETRY_EXHAUSTED"
    else:
        updated["state"] = "RETRY_PENDING"
    return updated
