from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .episodes import EpisodeStore
from .journal import KnowledgeJournal
from .learning import run_learning_cycle
from .snapshot import export_knowledge_snapshot


def run_knowledge_cycle(
    *,
    root: str | Path,
    replay_results: list[dict[str, Any]],
    created_at: datetime | None = None,
) -> dict[str, Any]:
    root = Path(root)
    episodes = EpisodeStore(root / "episodes")
    knowledge = KnowledgeJournal(root / "knowledge" / "journal.jsonl")

    ingested = []
    for result in replay_results:
        ingested.append(
            episodes.ingest(
                episode=result["episode"],
                score=result["score"],
                stream="REPLAY",
                created_at=created_at,
            )
        )

    report = run_learning_cycle(
        episode_records=episodes.list("REPLAY"),
        journal=knowledge,
        stream="REPLAY",
        created_at=created_at,
    )
    snapshot = export_knowledge_snapshot(
        records=knowledge.read_all(),
        canonical_policies=[],
        research_items=[],
        created_at=created_at,
    )
    return {
        "ingested_episode_records": ingested,
        "learning_report": report,
        "knowledge_snapshot": snapshot,
    }
