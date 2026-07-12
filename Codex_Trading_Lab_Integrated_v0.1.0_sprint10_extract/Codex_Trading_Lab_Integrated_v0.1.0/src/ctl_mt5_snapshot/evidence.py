from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import assert_safe_run_id, atomic_write_json, parse_time, sha256_bytes, sha256_json


class EvidenceCollision(RuntimeError):
    pass


class EvidenceStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _run_root(self, kind: str, capture_time: str, run_id: str) -> Path:
        assert_safe_run_id(run_id)
        day = parse_time(capture_time)
        return self.root / kind / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.day:02d}" / run_id

    def _write_once(self, path: Path, data: bytes) -> str:
        digest = sha256_bytes(data)
        if path.exists():
            existing = sha256_bytes(path.read_bytes())
            if existing == digest:
                return digest
            raise EvidenceCollision(f"Append-only collision at {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(data)
        temp.replace(path)
        return digest

    def write_raw_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        run_id = snapshot["run_id"]
        capture_time = snapshot["capture_time"]
        raw_dir = self._run_root("raw", capture_time, run_id)
        payload = json.dumps(snapshot, indent=2, sort_keys=True).encode("utf-8")
        try:
            raw_hash = self._write_once(raw_dir / "snapshot.json", payload)
            manifest = {
                "run_id": run_id,
                "snapshot_id": snapshot["snapshot_id"],
                "symbol": snapshot["symbol"],
                "source": snapshot["source"],
                "capture_time": capture_time,
                "raw_sha256": raw_hash,
                "trade_write_enabled": False,
            }
            manifest_hash = self._write_once(raw_dir / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
            latest = self.root / "latest" / "raw_snapshot.json"
            atomic_write_json(latest, {"run_id": run_id, "snapshot_id": snapshot["snapshot_id"], "manifest": str(raw_dir / "manifest.json"), "manifest_sha256": manifest_hash})
            return {"status": "RAW_STORED", "path": str(raw_dir), "raw_sha256": raw_hash, "manifest_sha256": manifest_hash}
        except EvidenceCollision as exc:
            quarantine = self._run_root("quarantine", capture_time, run_id)
            quarantine.mkdir(parents=True, exist_ok=True)
            (quarantine / "collision_snapshot.json").write_bytes(payload)
            atomic_write_json(quarantine / "quarantine_manifest.json", {"reason": str(exc), "run_id": run_id, "snapshot_id": snapshot.get("snapshot_id"), "content_sha256": sha256_bytes(payload)})
            return {"status": "QUARANTINED", "path": str(quarantine), "reason": str(exc)}

    def write_normalized(self, *, snapshot: dict[str, Any], name: str, payload: dict[str, Any], raw_sha256: str) -> dict[str, Any]:
        run_id = snapshot["run_id"]
        normalized_dir = self._run_root("normalized", snapshot["capture_time"], run_id)
        body = {"run_id": run_id, "snapshot_id": snapshot["snapshot_id"], "source_raw_sha256": raw_sha256, "payload": payload}
        data = json.dumps(body, indent=2, sort_keys=True).encode("utf-8")
        digest = self._write_once(normalized_dir / f"{name}.json", data)
        return {"status": "NORMALIZED_STORED", "path": str(normalized_dir / f"{name}.json"), "sha256": digest, "source_raw_sha256": raw_sha256}

    def bundle(self, destination: str | Path) -> str:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        base = shutil.make_archive(str(destination.with_suffix("")), "zip", self.root)
        return base
