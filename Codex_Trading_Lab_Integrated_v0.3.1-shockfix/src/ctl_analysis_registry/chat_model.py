"""Freeze structured Chat Model claims without reconstructing prior prose."""

from __future__ import annotations

from typing import Any

from .recorder import _freeze_claim


def freeze_chat_model_view(
    envelope: dict[str, Any],
    snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    if envelope.get("snapshot_id") != snapshot.get("snapshot_id"):
        raise ValueError("Chat Model snapshot binding mismatch")
    if envelope.get("system") != "CHAT_MODEL":
        raise ValueError("Chat Model envelope system must be CHAT_MODEL")
    claims = envelope.get("claims")
    if not isinstance(claims, list):
        raise ValueError("Chat Model envelope claims must be a list")
    analysis_id = str(envelope.get("analysis_id") or "")
    view_id = str(envelope.get("view_id") or "")
    if not analysis_id or not view_id:
        raise ValueError("Chat Model analysis_id and view_id are required")
    return [
        _freeze_claim(
            claim,
            snapshot=snapshot,
            analysis_id=analysis_id,
            view_id=view_id,
            system="CHAT_MODEL",
            engine_version=str(envelope.get("engine_version") or "CHAT_MODEL_UNKNOWN"),
        )
        for claim in claims
    ]
