from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json


def _payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("payload", data)


def summarize_candidate_lifecycle(normalized_root: str | Path) -> dict[str, Any]:
    observations: list[tuple[str, dict[str, Any]]] = []
    for path in Path(normalized_root).rglob("decision_state.json"):
        payload = _payload(path)
        observations.append((payload.get("market_packet", {}).get("generated_at", payload.get("snapshot_id", "")), payload))
    observations.sort(key=lambda item: item[0])
    histories: dict[str, dict[str, Any]] = {}
    transitions: Counter[str] = Counter()
    total_observations = 0
    for timestamp, payload in observations:
        for candidate in payload.get("entry_packet", {}).get("candidates", []):
            candidate_id = candidate.get("candidate_id", "UNKNOWN")
            status = candidate.get("status", "UNKNOWN")
            total_observations += 1
            history = histories.setdefault(candidate_id, {
                "candidate_id": candidate_id,
                "scenario_id": candidate.get("scenario_id"),
                "side": candidate.get("side"),
                "entry_type": candidate.get("entry_type"),
                "first_seen": timestamp,
                "last_seen": timestamp,
                "observations": 0,
                "status_sequence": [],
            })
            if history["status_sequence"]:
                previous = history["status_sequence"][-1]["status"]
                if previous != status:
                    transitions[f"{previous}->{status}"] += 1
            history["last_seen"] = timestamp
            history["observations"] += 1
            history["status_sequence"].append({"timestamp": timestamp, "status": status})
    for history in histories.values():
        history["final_status"] = history["status_sequence"][-1]["status"] if history["status_sequence"] else "UNKNOWN"
        history["status_transition_count"] = sum(
            1 for before, after in zip(history["status_sequence"], history["status_sequence"][1:])
            if before["status"] != after["status"]
        )
        history["stable_wait"] = history["final_status"] == "WAIT" and history["status_transition_count"] == 0
    status_counts = Counter(history["final_status"] for history in histories.values())
    return {
        "schema_version": "0.1.0",
        "mode": "CANDIDATE_LIFECYCLE_QA_ONLY",
        "snapshots_analyzed": len(observations),
        "total_candidate_observations": total_observations,
        "unique_candidate_count": len(histories),
        "status_transition_counts": dict(sorted(transitions.items())),
        "final_status_counts": dict(sorted(status_counts.items())),
        "stable_wait_candidate_count": sum(1 for history in histories.values() if history["stable_wait"]),
        "candidate_churn_ratio": None if total_observations == 0 else round(len(histories) / total_observations, 6),
        "candidates": sorted(histories.values(), key=lambda item: item["candidate_id"]),
        "execution_permission_effect": "NONE",
        "limitations": [
            "Lifecycle observation is not an outcome label and does not establish expectancy.",
            "Candidate IDs are semantic identities; a changed zone identity can create a new lifecycle.",
        ],
    }
