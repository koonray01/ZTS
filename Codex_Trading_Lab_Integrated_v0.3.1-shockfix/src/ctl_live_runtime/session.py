from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import atomic_write_json, iso_z, load_json, sanitize_id, utc_now


ALLOWED_TRANSITIONS = {
    "CREATED": {"STARTING", "STOPPED"},
    "STARTING": {"ACTIVE", "LOCKED", "STOPPED"},
    "ACTIVE": {"PAUSED", "LOCKED", "STOPPED"},
    "PAUSED": {"ACTIVE", "LOCKED", "STOPPED"},
    "LOCKED": {"ACTIVE", "STOPPED"},
    "STOPPED": set(),
}


class InvalidSessionTransition(RuntimeError):
    pass


class SessionController:
    def __init__(self, state_path: str | Path, symbol: str, now: datetime | None = None):
        self.state_path = Path(state_path)
        existing = load_json(self.state_path)
        if existing:
            self.state = existing
        else:
            created = now or utc_now()
            self.state = {
                "schema_version": "0.1.0",
                "session_id": sanitize_id(f"SESSION_{symbol}_{iso_z(created)}"),
                "symbol": symbol,
                "state": "CREATED",
                "created_at": iso_z(created),
                "updated_at": iso_z(created),
                "new_entries_allowed": False,
                "position_monitoring_active": True,
                "processed_snapshots": 0,
                "last_snapshot_id": None,
                "active_locks": [],
                "health": {"status": "HEALTHY", "issues": []},
            }
            self._persist()

    def _persist(self) -> None:
        atomic_write_json(self.state_path, self.state)

    def transition(self, target: str, *, now: datetime | None = None) -> dict[str, Any]:
        current = self.state["state"]
        if target not in ALLOWED_TRANSITIONS[current]:
            raise InvalidSessionTransition(f"{current} -> {target} is not allowed")
        self.state["state"] = target
        self.state["updated_at"] = iso_z(now or utc_now())
        self.state["new_entries_allowed"] = target == "ACTIVE"
        self.state["position_monitoring_active"] = target != "STOPPED"
        self._persist()
        return self.state

    def add_lock(self, code: str, *, critical: bool = True, now: datetime | None = None) -> None:
        if code not in self.state["active_locks"]:
            self.state["active_locks"].append(code)
        self.state["health"]["status"] = "CRITICAL" if critical else "DEGRADED"
        if code not in self.state["health"]["issues"]:
            self.state["health"]["issues"].append(code)
        if self.state["state"] not in {"LOCKED", "STOPPED"}:
            if "LOCKED" in ALLOWED_TRANSITIONS[self.state["state"]]:
                self.transition("LOCKED", now=now)
            else:
                self._persist()
        else:
            self._persist()

    def clear_lock(self, code: str, *, now: datetime | None = None) -> None:
        self.state["active_locks"] = [item for item in self.state["active_locks"] if item != code]
        self.state["health"]["issues"] = [item for item in self.state["health"]["issues"] if item != code]
        self.state["health"]["status"] = "HEALTHY" if not self.state["active_locks"] else "DEGRADED"
        self.state["updated_at"] = iso_z(now or utc_now())
        self._persist()

    def record_snapshot(self, snapshot_id: str, *, now: datetime | None = None) -> None:
        self.state["processed_snapshots"] += 1
        self.state["last_snapshot_id"] = snapshot_id
        self.state["updated_at"] = iso_z(now or utc_now())
        self._persist()
