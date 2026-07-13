from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import canonical_json, iso_z, sha256_json


class AuditJournal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, payload: dict[str, Any], created_at: datetime | None = None) -> dict[str, Any]:
        records = self.read_all()
        previous_hash = records[-1]["record_hash"] if records else "GENESIS"
        sequence = len(records) + 1
        record_without_hash = {
            "sequence": sequence,
            "event_type": event_type,
            "payload_hash": sha256_json(payload),
            "previous_record_hash": previous_hash,
            "created_at": iso_z(created_at or datetime.now(timezone.utc)),
        }
        record = {
            **record_without_hash,
            "record_hash": sha256_json(record_without_hash),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
        return record

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [json.loads(line) for line in lines]


def verify_journal(path: str | Path) -> tuple[bool, list[str]]:
    journal = AuditJournal(path)
    errors = []
    previous_hash = "GENESIS"
    for expected_sequence, record in enumerate(journal.read_all(), start=1):
        if record["sequence"] != expected_sequence:
            errors.append(f"Sequence mismatch at record {expected_sequence}.")
        if record["previous_record_hash"] != previous_hash:
            errors.append(f"Previous hash mismatch at record {expected_sequence}.")
        without_hash = {key: value for key, value in record.items() if key != "record_hash"}
        expected_hash = sha256_json(without_hash)
        if record["record_hash"] != expected_hash:
            errors.append(f"Record hash mismatch at record {expected_sequence}.")
        previous_hash = record["record_hash"]
    return not errors, errors
