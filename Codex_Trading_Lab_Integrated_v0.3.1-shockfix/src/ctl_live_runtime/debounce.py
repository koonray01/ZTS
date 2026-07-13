from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import atomic_write_json, iso_z, load_json


class EventDebouncer:
    def __init__(self, state_path: str | Path, debounce_seconds: int = 60):
        self.state_path = Path(state_path)
        self.debounce_seconds = debounce_seconds
        self.state = load_json(self.state_path, default={"seen": {}})

    def accept(self, event_key: str, now: datetime) -> bool:
        seen_at = self.state["seen"].get(event_key)
        if seen_at:
            previous = datetime.fromisoformat(seen_at.replace("Z", "+00:00")).astimezone(timezone.utc)
            if (now - previous).total_seconds() < self.debounce_seconds:
                return False
        self.state["seen"][event_key] = iso_z(now)
        atomic_write_json(self.state_path, self.state)
        return True

    def seen_keys(self) -> set[str]:
        return set(self.state["seen"])
