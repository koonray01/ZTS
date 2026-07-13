from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .journal import KnowledgeJournal


class EpisodeStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _journal(self, stream: str) -> KnowledgeJournal:
        if stream not in {"REPLAY", "LIVE_SHADOW", "LIVE_EXECUTION"}:
            raise ValueError(f"Unsupported stream: {stream}")
        return KnowledgeJournal(self.root / f"{stream.lower()}.jsonl")

    def ingest(
        self,
        *,
        episode: dict[str, Any],
        score: dict[str, Any] | None,
        stream: str,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        if stream == "LIVE_EXECUTION" and episode.get("live_execution_credit") is False:
            raise ValueError("Replay/shadow episode cannot be ingested as LIVE_EXECUTION.")
        payload = {
            "episode": episode,
            "score": score,
            "entry_engine_credit": None if score is None else score.get("entry_engine_credit"),
        }
        refs = [
            episode.get("episode_id", "UNKNOWN_EPISODE"),
            episode.get("visible_snapshot_id", "UNKNOWN_SNAPSHOT"),
        ]
        return self._journal(stream).append(
            record_type="EPISODE",
            trust_tier="EPISODE_OBSERVATION",
            status="RECORDED",
            version=episode.get("case_version", "0.0.0"),
            stream=stream,
            source_refs=refs,
            payload=payload,
            created_at=created_at,
        )

    def list(self, stream: str) -> list[dict[str, Any]]:
        return self._journal(stream).read_all()

    def counts(self) -> dict[str, int]:
        return {
            stream: len(self.list(stream))
            for stream in ["REPLAY", "LIVE_SHADOW", "LIVE_EXECUTION"]
        }
