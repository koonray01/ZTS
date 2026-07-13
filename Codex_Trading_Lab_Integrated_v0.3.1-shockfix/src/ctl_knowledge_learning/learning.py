from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from .failure_kb import describe_failure
from .journal import KnowledgeJournal
from .utils import iso_z, sanitize_id, utc_now


def run_learning_cycle(
    *,
    episode_records: list[dict[str, Any]],
    journal: KnowledgeJournal,
    stream: str,
    observation_threshold: int = 2,
    hypothesis_threshold: int = 3,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    now = created_at or utc_now()
    failures = Counter()
    source_by_failure: dict[str, list[str]] = {}

    for record in episode_records:
        if record["stream"] != stream:
            raise ValueError("Learning cycle cannot mix streams.")
        score = record["payload"].get("score") or {}
        for failure in score.get("failure_modes", []):
            failures[failure] += 1
            source_by_failure.setdefault(failure, []).append(record["record_id"])

    observations = []
    hypotheses = []
    promotion_candidates = []

    for failure, count in sorted(failures.items()):
        if count < observation_threshold:
            continue
        details = describe_failure(failure)
        observation = journal.append(
            record_type="OBSERVATION",
            trust_tier="EPISODE_OBSERVATION",
            status="RECORDED",
            version="0.1.0",
            stream=stream,
            source_refs=source_by_failure[failure],
            payload={
                "failure_mode": failure,
                "count": count,
                "severity": details["severity"],
                "description": details["description"],
                "statement": f"{failure} appeared in {count} {stream} episodes.",
                "production_rule": False,
            },
            created_at=now,
            record_id=sanitize_id(f"OBS_{stream}_{failure}_{count}"),
        )
        observations.append(observation["record_id"])

        if count >= hypothesis_threshold:
            hypothesis = journal.append(
                record_type="HYPOTHESIS",
                trust_tier="HYPOTHESIS",
                status="PROPOSED",
                version="0.1.0",
                stream=stream,
                source_refs=[observation["record_id"]],
                payload={
                    "hypothesis": f"Reducing {failure} may improve process compliance.",
                    "failure_mode": failure,
                    "registered_experiment_required": True,
                    "production_rule": False,
                },
                created_at=now,
                record_id=sanitize_id(f"HYP_{stream}_{failure}_{count}"),
            )
            hypotheses.append(hypothesis["record_id"])
            if count >= 20:
                promotion_candidates.append(hypothesis["record_id"])

    episode_count = len(episode_records)
    edge_status = "INSUFFICIENT_EVIDENCE" if episode_count < 50 else "INCONCLUSIVE"

    return {
        "schema_version": "0.1.0",
        "report_id": sanitize_id(f"LEARNING_REPORT_{stream}_{iso_z(now)}"),
        "stream": stream,
        "episodes_processed": episode_count,
        "failure_counts": dict(failures),
        "observations_created": observations,
        "hypotheses_created": hypotheses,
        "promotion_candidates": promotion_candidates,
        "edge_status": edge_status,
        "created_at": iso_z(now),
    }
