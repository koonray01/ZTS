from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import canonical_json, iso_z, sanitize_id, sha256_json, utc_now


class KnowledgeJournal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def append(
        self,
        *,
        record_type: str,
        trust_tier: str,
        status: str,
        version: str,
        stream: str,
        source_refs: list[str],
        payload: dict[str, Any],
        created_at: datetime | None = None,
        record_id: str | None = None,
    ) -> dict[str, Any]:
        records = self.read_all()
        previous_hash = records[-1]["record_hash"] if records else "GENESIS"
        timestamp = created_at or utc_now()
        seed = {
            "record_type": record_type,
            "version": version,
            "stream": stream,
            "source_refs": source_refs,
            "payload": payload,
            "created_at": iso_z(timestamp),
        }
        body = {
            "schema_version": "0.1.0",
            "record_id": record_id or sanitize_id(
                f"{record_type}_{sha256_json(seed)[:20]}"
            ),
            "record_type": record_type,
            "trust_tier": trust_tier,
            "status": status,
            "version": version,
            "stream": stream,
            "source_refs": list(dict.fromkeys(source_refs)),
            "payload": payload,
            "created_at": iso_z(timestamp),
            "previous_record_hash": previous_hash,
        }
        record = {**body, "record_hash": sha256_json(body)}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
        return record


def verify_journal(path: str | Path) -> tuple[bool, list[str]]:
    journal = KnowledgeJournal(path)
    errors = []
    previous_hash = "GENESIS"
    for index, record in enumerate(journal.read_all(), start=1):
        if record["previous_record_hash"] != previous_hash:
            errors.append(f"Previous hash mismatch at record {index}.")
        body = {key: value for key, value in record.items() if key != "record_hash"}
        if record["record_hash"] != sha256_json(body):
            errors.append(f"Record hash mismatch at record {index}.")
        previous_hash = record["record_hash"]
    return not errors, errors
