from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import StateUnavailable
from .utils import atomic_write_json, load_json


class StateRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.state = load_json(self.path, default={"snapshots": {}})

    def put(self, snapshot_id: str, state: dict[str, Any]) -> None:
        self.state["snapshots"][snapshot_id] = state
        atomic_write_json(self.path, self.state)

    def get(self, snapshot_id: str) -> dict[str, Any]:
        try:
            return self.state["snapshots"][snapshot_id]
        except KeyError as exc:
            raise StateUnavailable(
                f"No worker state registered for snapshot {snapshot_id}."
            ) from exc
