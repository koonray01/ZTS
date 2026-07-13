from __future__ import annotations

from typing import Any

from .trust import production_authoritative, trust_rank


class KnowledgeQuery:
    def __init__(self, records: list[dict[str, Any]]):
        self.records = list(records)

    def search(
        self,
        *,
        text: str = "",
        record_types: set[str] | None = None,
        stream: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        needle = text.lower().strip()
        results = []
        for record in self.records:
            if record_types and record["record_type"] not in record_types:
                continue
            if stream and record["stream"] != stream:
                continue
            haystack = (
                record["record_id"]
                + " "
                + record["status"]
                + " "
                + str(record["payload"])
            ).lower()
            if needle and needle not in haystack:
                continue
            results.append(
                {
                    **record,
                    "production_authoritative": production_authoritative(record),
                    "trust_rank": trust_rank(record["trust_tier"]),
                }
            )
        results.sort(
            key=lambda item: (
                -item["trust_rank"],
                item["record_type"],
                item["record_id"],
            )
        )
        return results[:limit]
