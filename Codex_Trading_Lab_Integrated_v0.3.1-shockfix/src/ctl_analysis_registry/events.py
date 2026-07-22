"""Hash-chained registry event construction and validation."""

from __future__ import annotations

from typing import Any

from .identity import canonical_json, sha256_hex
from .contracts import PHASE2_EVENT_TYPES, V2_SCHEMA_VERSION


SCHEMA_VERSION = "ANALYSIS_REGISTRY_EVENT_V0_1"
HASH_EXCLUDED_FIELDS = {"event_hash"}


def _hash_material(event: dict[str, Any]) -> str:
    return canonical_json({key: value for key, value in event.items() if key not in HASH_EXCLUDED_FIELDS})


def event_hash(event: dict[str, Any]) -> str:
    """Calculate the digest over all event content except its stored digest."""

    return sha256_hex(_hash_material(event))


def build_event(payload: dict[str, Any], *, previous_hash: str | None) -> dict[str, Any]:
    """Build one immutable event from metadata and a payload."""

    required = {
        "event_id", "event_type", "event_time", "decision_time", "source_class",
        "integrity_tier", "producer", "payload",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"missing event fields: {', '.join(missing)}")
    event = {
        "schema_version": SCHEMA_VERSION,
        **payload,
        "previous_event_hash": previous_hash,
    }
    event["event_hash"] = event_hash(event)
    return event


def build_v2_event(fields: dict[str, Any], *, previous_hash: str | None) -> dict[str, Any]:
    """Build one Phase 2 event without changing Phase 1 construction or hashing."""

    required = {
        "event_id", "event_type", "event_time", "decision_time", "source_class",
        "integrity_tier", "producer", "payload",
    }
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"missing event fields: {', '.join(missing)}")
    if fields["event_type"] not in PHASE2_EVENT_TYPES:
        raise ValueError(f"unsupported Phase 2 event type: {fields['event_type']}")
    event = {
        "schema_version": V2_SCHEMA_VERSION,
        **fields,
        "previous_event_hash": previous_hash,
    }
    event["event_hash"] = event_hash(event)
    return event


def validate_event_chain(events: list[dict[str, Any]]) -> list[str]:
    """Return deterministic errors for malformed or tampered event chains."""

    errors: list[str] = []
    seen: set[str] = set()
    previous_hash: str | None = None
    for index, event in enumerate(events):
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            errors.append(f"event[{index}] missing event_id")
        elif event_id in seen:
            errors.append(f"duplicate event_id: {event_id}")
        else:
            seen.add(event_id)
        if event.get("previous_event_hash") != previous_hash:
            errors.append(f"event[{index}] previous_event_hash mismatch")
        stored_hash = event.get("event_hash")
        if not isinstance(stored_hash, str) or stored_hash != event_hash(event):
            errors.append(f"event[{index}] hash mismatch")
        previous_hash = stored_hash if isinstance(stored_hash, str) else None
    return errors
