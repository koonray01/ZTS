from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .skills import SKILL_REGISTRY
from .utils import iso_z, sanitize_id, sha256_json


EVENT_ROUTING = {
    "MARKET_STATE_CHANGED": ("MARKET_UPDATE", "ctl-market-read", "NORMAL", 1800),
    "SHOCK_DETECTED": ("MARKET_UPDATE", "ctl-live-event-review", "CRITICAL", 1400),
    "SCENARIO_RANK_CHANGED": ("MARKET_UPDATE", "ctl-scenario-planner", "HIGH", 1800),
    "ENTRY_WINDOW_OPENED": ("ENTRY_REVIEW", "ctl-entry-evaluator", "HIGH", 1600),
    "ENTRY_INVALIDATED": ("ENTRY_REVIEW", "ctl-entry-evaluator", "HIGH", 1200),
    "EVIDENCE_ANOMALY": ("EVIDENCE_AUDIT", "ctl-evidence-audit", "HIGH", 1800),
}


def build_codex_job(
    *,
    snapshot_id: str,
    event_types: list[str],
    input_refs: list[str],
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    routed = [EVENT_ROUTING[event] for event in event_types if event in EVENT_ROUTING]
    if not routed:
        routed = [("MARKET_UPDATE", "ctl-live-event-review", "LOW", 900)]

    priority_order = {"LOW": 0, "NORMAL": 1, "HIGH": 2, "CRITICAL": 3}
    job_type, skill_id, priority, token_budget = max(
        routed,
        key=lambda item: priority_order[item[2]],
    )
    skill = SKILL_REGISTRY[skill_id]
    seed = {
        "snapshot_id": snapshot_id,
        "event_types": sorted(set(event_types)),
        "skill_id": skill_id,
        "created_at": iso_z(current_time),
    }
    return {
        "schema_version": "0.1.0",
        "job_id": sanitize_id(f"JOB_{sha256_json(seed)[:20]}"),
        "job_type": job_type,
        "skill_id": skill_id,
        "skill_version": skill["version"],
        "snapshot_id": snapshot_id,
        "priority": priority,
        "reason_codes": sorted(set(event_types)) or ["STATE_REFRESH"],
        "input_refs": list(dict.fromkeys(input_refs)),
        "token_budget": token_budget,
        "allowed_tools": skill["allowed_tools"],
        "prohibited_actions": [
            "Do not place, modify, cancel or close orders.",
            "Do not modify raw evidence or deterministic outputs.",
            "Do not change production policy or skill versions.",
        ],
        "created_at": iso_z(current_time),
    }
