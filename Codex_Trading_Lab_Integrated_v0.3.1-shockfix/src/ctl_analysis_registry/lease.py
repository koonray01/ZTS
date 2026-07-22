"""Portable exclusive-create writer lease for the Analysis Registry."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class LeaseError(RuntimeError):
    """Base registry lease error."""


class LeaseBusyError(LeaseError):
    """Raised when another writer owns a live lease."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise LeaseError("registry lease heartbeat is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LeaseError("registry lease heartbeat is invalid") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _write_descriptor(descriptor: int, payload: dict[str, Any]) -> None:
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())


def _append_operation(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab", buffering=0) as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


@dataclass
class RegistryWriterLease:
    path: Path
    owner_id: str
    acquired_at: datetime
    ttl_seconds: int

    @classmethod
    def acquire(
        cls,
        path: str | Path,
        owner_id: str,
        ttl_seconds: int,
        *,
        now: datetime | None = None,
        operation_log: str | Path | None = None,
    ) -> "RegistryWriterLease":
        if not owner_id:
            raise ValueError("owner_id is required")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        acquired_at = now or _utc_now()
        payload = {
            "owner_id": owner_id,
            "acquired_at": acquired_at.isoformat(),
            "heartbeat_at": acquired_at.isoformat(),
            "ttl_seconds": ttl_seconds,
        }
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise LeaseBusyError("registry lease exists but cannot be verified") from exc
            heartbeat = _parse_time(current.get("heartbeat_at"))
            current_ttl = int(current.get("ttl_seconds", 0) or 0)
            if acquired_at <= heartbeat + timedelta(seconds=current_ttl):
                raise LeaseBusyError(f"registry lease held by {current.get('owner_id', 'UNKNOWN')}")
            if operation_log is not None:
                _append_operation(
                    Path(operation_log),
                    {
                        "event": "STALE_REGISTRY_LEASE_RECOVERED",
                        "event_time": acquired_at.isoformat(),
                        "previous_owner_id": current.get("owner_id"),
                        "new_owner_id": owner_id,
                        "previous_heartbeat_at": current.get("heartbeat_at"),
                    },
                )
            try:
                path.unlink()
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except (FileNotFoundError, FileExistsError) as exc:
                raise LeaseBusyError("registry lease changed during stale recovery") from exc
        _write_descriptor(descriptor, payload)
        return cls(path=path, owner_id=owner_id, acquired_at=acquired_at, ttl_seconds=ttl_seconds)

    def _read_owned(self) -> dict[str, Any]:
        try:
            current = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LeaseError("registry lease is missing or invalid") from exc
        if current.get("owner_id") != self.owner_id:
            raise LeaseBusyError("registry lease owner changed")
        return current

    def heartbeat(self, *, now: datetime | None = None) -> None:
        current = self._read_owned()
        current["heartbeat_at"] = (now or _utc_now()).isoformat()
        temporary = self.path.with_name(f".{self.path.name}.{self.owner_id}.tmp")
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            _write_descriptor(descriptor, current)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def release(self) -> None:
        self._read_owned()
        self.path.unlink()
