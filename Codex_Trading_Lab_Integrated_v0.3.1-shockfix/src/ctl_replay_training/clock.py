from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ReplayClock:
    steps: tuple[dict, ...]
    index: int = 0

    @property
    def current_step(self) -> dict:
        return self.steps[self.index]

    @property
    def replay_time(self) -> datetime:
        from .utils import parse_time
        return parse_time(self.current_step["replay_time"])

    def can_advance(self) -> bool:
        return self.index < len(self.steps) - 1

    def advance(self) -> dict:
        if not self.can_advance():
            raise StopIteration("Replay is already at the final visible step.")
        self.index += 1
        return self.current_step
