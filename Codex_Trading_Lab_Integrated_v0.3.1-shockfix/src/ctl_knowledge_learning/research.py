from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import atomic_write_json, iso_z, load_json, sanitize_id, utc_now


ALLOWED_TRANSITIONS = {
    "PROPOSED": {"TESTING", "REJECTED", "DEPRECATED"},
    "TESTING": {"SUPPORTED", "INCONCLUSIVE", "REJECTED", "DEPRECATED"},
    "SUPPORTED": {"DEPRECATED"},
    "INCONCLUSIVE": {"TESTING", "DEPRECATED"},
    "REJECTED": {"DEPRECATED"},
    "DEPRECATED": set(),
}


class InvalidResearchTransition(RuntimeError):
    pass


class ResearchRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.state = load_json(self.path, default={"items": {}})

    def _persist(self) -> None:
        atomic_write_json(self.path, self.state)

    def create(
        self,
        *,
        title: str,
        hypothesis: str,
        definition_version: str,
        stream: str,
        source_refs: list[str],
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        now = created_at or utc_now()
        research_id = sanitize_id(f"RESEARCH_{title}_{definition_version}")
        if research_id in self.state["items"]:
            raise ValueError(f"Research item already exists: {research_id}")
        item = {
            "schema_version": "0.1.0",
            "research_id": research_id,
            "title": title,
            "definition_version": definition_version,
            "status": "PROPOSED",
            "hypothesis": hypothesis,
            "stream": stream,
            "metrics": {},
            "cohort": {
                "triggered_cases": 0,
                "validation_cases": 0,
                "locked_oos_cases": 0,
            },
            "source_refs": list(dict.fromkeys(source_refs)),
            "created_at": iso_z(now),
            "updated_at": iso_z(now),
        }
        self.state["items"][research_id] = item
        self._persist()
        return item

    def transition(
        self,
        research_id: str,
        target: str,
        *,
        metrics: dict[str, Any] | None = None,
        cohort: dict[str, int] | None = None,
        updated_at: datetime | None = None,
    ) -> dict[str, Any]:
        item = self.state["items"][research_id]
        current = item["status"]
        if target not in ALLOWED_TRANSITIONS[current]:
            raise InvalidResearchTransition(f"{current} -> {target} is not allowed")
        item["status"] = target
        if metrics is not None:
            item["metrics"] = metrics
        if cohort is not None:
            item["cohort"] = cohort
        item["updated_at"] = iso_z(updated_at or utc_now())
        self._persist()
        return item

    def get(self, research_id: str) -> dict[str, Any]:
        return dict(self.state["items"][research_id])

    def list(self) -> list[dict[str, Any]]:
        return list(self.state["items"].values())
