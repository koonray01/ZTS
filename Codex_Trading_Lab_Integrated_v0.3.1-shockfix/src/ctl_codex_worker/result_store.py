from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import canonical_json, iso_z, sha256_json, utc_now


class ResultStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def append(
        self,
        result: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        existing = next(
            (item for item in self.records() if item["result"]["job_id"] == result["job_id"]),
            None,
        )
        if existing:
            return False, existing
        records = self.records()
        previous = records[-1]["record_hash"] if records else "GENESIS"
        body = {
            "sequence": len(records) + 1,
            "result": result,
            "created_at": iso_z(now or utc_now()),
            "previous_record_hash": previous,
        }
        record = {**body, "record_hash": sha256_json(body)}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
        return True, record

    def by_job(self, job_id: str) -> dict[str, Any] | None:
        record = next(
            (item for item in self.records() if item["result"]["job_id"] == job_id),
            None,
        )
        return None if record is None else record["result"]


def verify_result_store(path: str | Path) -> tuple[bool, list[str]]:
    store = ResultStore(path)
    errors = []
    previous = "GENESIS"
    for index, record in enumerate(store.records(), start=1):
        if record["sequence"] != index:
            errors.append(f"Sequence mismatch at result {index}.")
        if record["previous_record_hash"] != previous:
            errors.append(f"Previous hash mismatch at result {index}.")
        body = {key: value for key, value in record.items() if key != "record_hash"}
        if record["record_hash"] != sha256_json(body):
            errors.append(f"Record hash mismatch at result {index}.")
        previous = record["record_hash"]
    return not errors, errors
