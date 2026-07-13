from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .utils import iso_z, sanitize_id, sha256_json


def build_episode_bundle(
    *,
    case_manifest: dict[str, Any],
    visible_snapshot_id: str,
    submission: dict[str, Any],
    visible_packet: dict[str, Any],
    hidden_outcome: dict[str, Any],
    score: dict[str, Any],
    created_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "episode_id": sanitize_id(
            f"EPISODE_{case_manifest['case_id']}_{submission['submission_id']}"
        ),
        "case_id": case_manifest["case_id"],
        "case_version": case_manifest["case_version"],
        "partition": case_manifest["partition"],
        "visible_snapshot_id": visible_snapshot_id,
        "submission_hash": sha256_json(submission),
        "visible_packet_hash": sha256_json(visible_packet),
        "outcome_hash": sha256_json(hidden_outcome),
        "score_hash": sha256_json(score),
        "created_at": iso_z(created_at or datetime.now(timezone.utc)),
        "live_execution_credit": False,
    }
