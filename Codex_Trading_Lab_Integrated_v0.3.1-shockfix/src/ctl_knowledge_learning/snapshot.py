from __future__ import annotations

from datetime import datetime
from typing import Any

from .utils import iso_z, sha256_json, utc_now


def export_knowledge_snapshot(
    *,
    records: list[dict[str, Any]],
    canonical_policies: list[dict[str, Any]],
    research_items: list[dict[str, Any]],
    created_at: datetime | None = None,
) -> dict[str, Any]:
    payload = {
        "records": sorted(records, key=lambda item: item["record_id"]),
        "canonical_policies": sorted(
            canonical_policies,
            key=lambda item: (item["policy_id"], item["version"]),
        ),
        "research_items": sorted(
            research_items,
            key=lambda item: item["research_id"],
        ),
    }
    return {
        "schema_version": "0.1.0",
        "created_at": iso_z(created_at or utc_now()),
        "record_count": len(records),
        "canonical_policy_count": len(canonical_policies),
        "research_item_count": len(research_items),
        "payload_hash": sha256_json(payload),
        "payload": payload,
        "production_mutation_allowed": False,
    }
