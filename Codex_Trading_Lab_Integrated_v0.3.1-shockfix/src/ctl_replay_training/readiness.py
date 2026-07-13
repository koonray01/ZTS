from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json


def _payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("payload", data)


def explain_candidate_readiness(normalized_root: str | Path) -> dict[str, Any]:
    paths = sorted(Path(normalized_root).rglob("decision_state.json"))
    status: Counter[str] = Counter()
    sides: Counter[str] = Counter()
    entry_types: Counter[str] = Counter()
    triggers: Counter[str] = Counter()
    missing: Counter[str] = Counter()
    requirements: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    scenario_statuses: Counter[str] = Counter()
    scenario_events: Counter[str] = Counter()
    scenario_missing: Counter[str] = Counter()
    snapshots = 0
    ready_snapshots = 0
    for path in paths:
        payload = _payload(path)
        snapshots += 1
        for scenario in payload.get("scenario_packet", {}).get("scenarios", []):
            scenario_statuses[scenario.get("status", "UNKNOWN")] += 1
            for event in scenario.get("path", []):
                scenario_events[f"{event.get('event', 'UNKNOWN')}={event.get('state', 'UNKNOWN')}"] += 1
            for event in scenario.get("missing_events", []):
                scenario_missing[event] += 1
        snapshot_ready = False
        for candidate in payload.get("entry_packet", {}).get("candidates", []):
            candidate_status = candidate.get("status", "UNKNOWN")
            status[candidate_status] += 1
            sides[candidate.get("side", "UNKNOWN")] += 1
            entry_types[candidate.get("entry_type", "UNKNOWN")] += 1
            triggers[candidate.get("trigger", {}).get("status", "UNKNOWN")] += 1
            for condition in candidate.get("missing_conditions", []):
                missing[condition] += 1
            for requirement in candidate.get("hard_requirements", []):
                requirements[f"{requirement.get('requirement_id', 'UNKNOWN')}={requirement.get('status', 'UNKNOWN')}"] += 1
            location_status = next(
                (item.get("status") for item in candidate.get("hard_requirements", []) if item.get("requirement_id") == "LOCATION"),
                "UNKNOWN",
            )
            locations[location_status] += 1
            snapshot_ready = snapshot_ready or candidate_status == "READY_FOR_PERMISSION_REVIEW"
        if snapshot_ready:
            ready_snapshots += 1
    readiness = "READY_CANDIDATE_OBSERVED" if status.get("READY_FOR_PERMISSION_REVIEW", 0) else "NO_READY_CANDIDATE"
    return {
        "schema_version": "0.1.0",
        "mode": "READINESS_DIAGNOSTIC_QA_ONLY",
        "snapshots_analyzed": snapshots,
        "readiness": readiness,
        "ready_candidate_count": status.get("READY_FOR_PERMISSION_REVIEW", 0),
        "snapshots_with_ready_candidate": ready_snapshots,
        "status_counts": dict(sorted(status.items())),
        "side_counts": dict(sorted(sides.items())),
        "entry_type_counts": dict(sorted(entry_types.items())),
        "trigger_status_counts": dict(sorted(triggers.items())),
        "missing_condition_counts": dict(sorted(missing.items())),
        "hard_requirement_counts": dict(sorted(requirements.items())),
        "location_requirement_counts": dict(sorted(locations.items())),
        "scenario_status_counts": dict(sorted(scenario_statuses.items())),
        "scenario_event_state_counts": dict(sorted(scenario_events.items())),
        "scenario_missing_event_counts": dict(sorted(scenario_missing.items())),
        "execution_permission_effect": "NONE",
        "limitations": [
            "This report explains deterministic suppression; it does not create or promote candidates.",
            "A WAIT candidate remains non-actionable until all hard requirements and trigger conditions pass.",
        ],
    }
