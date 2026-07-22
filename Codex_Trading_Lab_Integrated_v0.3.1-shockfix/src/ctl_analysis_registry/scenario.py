"""Canonical ordered-event scenario outcome evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .identity import stable_id


SUPPORTED_EVENTS = {
    "CLOSED_ABOVE", "CLOSED_BELOW", "TOUCHED_BAND", "ENTERED_BAND",
    "EXITED_BAND", "INVALIDATION_HIT",
}


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _matches(rule: dict[str, Any], event: dict[str, Any]) -> bool:
    event_type = rule.get("event_type")
    if event_type not in SUPPORTED_EVENTS or event.get("event_type") != event_type:
        return False
    price = event.get("price")
    if event_type == "CLOSED_ABOVE":
        return isinstance(price, (int, float)) and price > rule.get("level", float("inf"))
    if event_type == "CLOSED_BELOW":
        return isinstance(price, (int, float)) and price < rule.get("level", float("-inf"))
    if event_type in {"TOUCHED_BAND", "ENTERED_BAND"}:
        return (
            isinstance(price, (int, float))
            and isinstance(rule.get("lower"), (int, float))
            and isinstance(rule.get("upper"), (int, float))
            and rule["lower"] <= price <= rule["upper"]
        )
    if event_type == "EXITED_BAND":
        return (
            isinstance(price, (int, float))
            and isinstance(rule.get("lower"), (int, float))
            and isinstance(rule.get("upper"), (int, float))
            and not rule["lower"] <= price <= rule["upper"]
        )
    return True


def label_scenario(
    decision: dict[str, Any],
    job: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    base = {
        "outcome_id": stable_id("MODEL_OUTCOME", decision["decision_id"], job["horizon"], decision["labeling_policy_version"]),
        "decision_id": decision["decision_id"], "decision_type": "SCENARIO",
        "system": decision["system"], "horizon": job["horizon"],
        "original_policy_version": decision["labeling_policy_version"],
        "evidence_refs": list(evidence.get("evidence_refs", [])),
        "safety": dict(decision.get("safety", {})),
    }
    qc = evidence.get("qc") if isinstance(evidence.get("qc"), dict) else {}
    if qc.get("status") != "PASS":
        return {**base, "classification": "INVALID_INPUT", "completion_ratio": 0.0, "reason_codes": list(qc.get("reasons", []))}
    rules = decision.get("rules") if isinstance(decision.get("rules"), dict) else {}
    steps = rules.get("success") if isinstance(rules.get("success"), list) else []
    required = sorted(
        [step for step in steps if isinstance(step, dict) and step.get("required", True)],
        key=lambda step: (int(step.get("sequence", 0)), str(step.get("step_id", ""))),
    )
    if not required or any(step.get("event_type") not in SUPPORTED_EVENTS for step in required):
        return {**base, "classification": "INVALID_INPUT", "completion_ratio": 0.0, "reason_codes": ["SCENARIO_GRAMMAR_INVALID"]}
    events = sorted(
        [event for event in evidence.get("events", []) if isinstance(event, dict) and isinstance(event.get("event_time"), str)],
        key=lambda event: (_time(event["event_time"]), str(event.get("event_id", ""))),
    )
    completed: list[dict[str, Any]] = []
    cursor: datetime | None = None
    for step in required:
        match = next(
            (
                event for event in events
                if (cursor is None or _time(event["event_time"]) > cursor) and _matches(step, event)
            ),
            None,
        )
        if match is None:
            break
        cursor = _time(match["event_time"])
        completed.append({"step_id": step.get("step_id"), "event_time": match["event_time"]})
    invalidation = rules.get("invalidation") if isinstance(rules.get("invalidation"), dict) else None
    invalidation_event = None
    if invalidation:
        invalidation_event = next((event for event in events if _matches(invalidation, event)), None)
    completion_time = cursor if len(completed) == len(required) else None
    invalidation_time = _time(invalidation_event["event_time"]) if invalidation_event else None
    ratio = len(completed) / len(required)
    if invalidation_time is not None and (completion_time is None or invalidation_time < completion_time):
        classification = "INVALIDATED"
    elif invalidation_time is not None and completion_time is not None and invalidation_time == completion_time:
        classification = "UNRESOLVED"
    elif completion_time is not None:
        classification = "CONFIRMED"
    elif evidence.get("expired") is True and completed:
        classification = "PARTIALLY_CONFIRMED"
    elif evidence.get("expired") is True:
        classification = "EXPIRED_UNTRIGGERED"
    else:
        classification = "UNRESOLVED"
    return {
        **base, "classification": classification, "completion_ratio": ratio,
        "completed_steps": completed,
        "invalidation_event_time": invalidation_event.get("event_time") if invalidation_event else None,
        "reason_codes": [],
    }
