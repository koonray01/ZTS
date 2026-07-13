from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Bar:
    bar_id: str
    open_time: str
    close_time: str
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    real_volume: int | None
    spread_points: int | None
    is_closed: bool

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Bar":
        return cls(
            bar_id=str(value["bar_id"]),
            open_time=str(value["open_time"]),
            close_time=str(value["close_time"]),
            open=float(value["open"]),
            high=float(value["high"]),
            low=float(value["low"]),
            close=float(value["close"]),
            tick_volume=int(value["tick_volume"]),
            real_volume=None if value.get("real_volume") is None else int(value["real_volume"]),
            spread_points=None if value.get("spread_points") is None else int(value["spread_points"]),
            is_closed=bool(value["is_closed"]),
        )


@dataclass(frozen=True)
class SensorContext:
    schema_version: str
    snapshot_id: str
    run_id: str
    symbol: str
    timeframe: str
    capture_time: str
    bars: tuple[Bar, ...]
    snapshot_evidence_refs: tuple[str, ...]
