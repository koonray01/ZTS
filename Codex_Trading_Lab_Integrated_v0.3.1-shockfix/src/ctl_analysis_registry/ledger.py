"""Append-only JSONL storage for registry events."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .events import validate_event_chain
from .identity import canonical_json


class LedgerError(RuntimeError):
    """Base error for invalid append-only ledger operations."""


class LedgerCollisionError(LedgerError):
    """Raised when an event ID is reused with different canonical content."""


class AppendOnlyLedger:
    """Small, deterministic JSONL ledger suitable for local evidence bundles."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise LedgerError(f"invalid JSON at line {line_number}") from exc
                    if not isinstance(value, dict):
                        raise LedgerError(f"event at line {line_number} is not an object")
                    events.append(value)
        except OSError as exc:
            raise LedgerError(f"cannot read ledger: {self.path}") from exc
        return events

    def contains_event(self, event_id: str) -> bool:
        return any(event.get("event_id") == event_id for event in self.read_all())

    def append(self, event: dict[str, Any]) -> str:
        return self.append_fsynced(event)

    def assert_complete_tail(self) -> None:
        """Reject a non-empty ledger whose last record lacks its newline commit marker."""

        if not self.path.exists() or self.path.stat().st_size == 0:
            return
        try:
            with self.path.open("rb") as handle:
                handle.seek(-1, os.SEEK_END)
                if handle.read(1) != b"\n":
                    raise LedgerError("partial ledger tail: final newline is missing")
        except OSError as exc:
            raise LedgerError(f"cannot inspect ledger tail: {self.path}") from exc

    def append_fsynced(self, event: dict[str, Any]) -> str:
        self.assert_complete_tail()
        events = self.read_all()
        errors = validate_event_chain(events)
        if errors:
            raise LedgerError("cannot append to invalid ledger: " + "; ".join(errors))

        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise LedgerError("event_id is required")
        existing = next((item for item in events if item.get("event_id") == event_id), None)
        if existing is not None:
            if canonical_json(existing) != canonical_json(event):
                raise LedgerCollisionError(f"event_id collision: {event_id}")
            return event_id

        previous_hash = events[-1].get("event_hash") if events else None
        if event.get("previous_event_hash") != previous_hash:
            raise LedgerError("previous_event_hash does not match ledger tail")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        try:
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise LedgerError(f"cannot append ledger: {self.path}") from exc
        appended = self.read_all()
        if not appended or appended[-1].get("event_hash") != event.get("event_hash"):
            raise LedgerError("appended event hash verification failed")
        return event_id
