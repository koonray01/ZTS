from __future__ import annotations

import copy
from typing import Any

from .utils import parse_time


class FutureLeakageError(RuntimeError):
    pass


def enforce_visible_snapshot(snapshot: dict[str, Any], replay_time: str) -> dict[str, Any]:
    cutoff = parse_time(replay_time)
    visible = copy.deepcopy(snapshot)
    for timeframe in visible["timeframes"]:
        filtered = [
            bar for bar in timeframe["bars"]
            if parse_time(bar["close_time"]) <= cutoff and bar["is_closed"]
        ]
        if not filtered:
            raise FutureLeakageError(
                f"No visible closed bars remain for {timeframe['timeframe']}."
            )
        timeframe["bars"] = filtered
        timeframe["returned_bars"] = len(filtered)
        timeframe["last_closed_bar_time"] = filtered[-1]["close_time"]

    future_refs = []
    for evidence in visible.get("indicator_evidence", []):
        available_at = evidence.get("first_available_at")
        if available_at and parse_time(available_at) > cutoff:
            future_refs.append(evidence.get("evidence_id", "UNKNOWN"))
    if future_refs:
        raise FutureLeakageError(
            "Snapshot contains future indicator evidence: " + ", ".join(future_refs)
        )
    return visible


def allowed_evidence_refs(decision_state: dict[str, Any]) -> set[str]:
    refs = set(decision_state["market_packet"]["evidence_refs"])
    refs.update(decision_state["scenario_packet"]["evidence_refs"])
    refs.update(decision_state["entry_packet"]["evidence_refs"])
    for result in decision_state["basic_eyes"]["results"]:
        refs.update(result.get("evidence_refs", []))
    for result in decision_state["advanced_eyes"]["results"]:
        refs.update(result.get("evidence_refs", []))
    return refs


def detect_future_reference(
    submission_refs: list[str],
    allowed_refs: set[str],
) -> list[str]:
    return [ref for ref in submission_refs if ref not in allowed_refs]
