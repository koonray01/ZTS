from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .utils import canonical_json, sha256_json


class PersistentJobQueue:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def enqueue(self, job: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        records = self._records()
        existing = next((item for item in records if item["job"]["job_id"] == job["job_id"]), None)
        if existing:
            return False, existing
        record = {
            "sequence": len(records) + 1,
            "record_type": "JOB_ENQUEUED",
            "job": job,
            "record_hash": sha256_json({"sequence": len(records) + 1, "job": job}),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
        return True, record

    def list_jobs(self) -> list[dict[str, Any]]:
        return [item["job"] for item in self._records()]

    def pending_count(self) -> int:
        return len(self._records())

    def verify(self) -> tuple[bool, list[str]]:
        errors = []
        for index, record in enumerate(self._records(), start=1):
            if record["sequence"] != index:
                errors.append(f"Sequence mismatch at {index}")
            expected = sha256_json({"sequence": index, "job": record["job"]})
            if record["record_hash"] != expected:
                errors.append(f"Hash mismatch at {index}")
        return not errors, errors
