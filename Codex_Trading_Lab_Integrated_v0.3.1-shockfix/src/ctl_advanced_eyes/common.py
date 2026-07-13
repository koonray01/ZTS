from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ctl_eyes.models import Bar, SensorContext
from ctl_eyes.utils import find_confirmed_swings, median, true_ranges


def atr_like_reference(bars: tuple[Bar, ...], lookback: int = 20) -> float | None:
    values = true_ranges(bars)
    return median(values[-lookback:])


def cluster_points(
    points: list[dict[str, Any]],
    tolerance: float,
) -> list[list[dict[str, Any]]]:
    if tolerance <= 0 or not points:
        return []
    ordered = sorted(points, key=lambda item: float(item["level"]))
    clusters: list[list[dict[str, Any]]] = [[ordered[0]]]
    for point in ordered[1:]:
        current = clusters[-1]
        center = sum(float(item["level"]) for item in current) / len(current)
        if abs(float(point["level"]) - center) <= tolerance:
            current.append(point)
        else:
            clusters.append([point])
    return clusters


def confirmed_swing_points(context: SensorContext) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return find_confirmed_swings(context.bars)


def zone_id(prefix: str, timeframe: str, index: int) -> str:
    return f"{prefix}_{timeframe}_{index:03d}"


def touches_zone(bar: Bar, lower: float, upper: float) -> bool:
    return bar.high >= lower and bar.low <= upper


def latest_close(context: SensorContext) -> float:
    return context.bars[-1].close


def bar_refs(bars: Iterable[Bar]) -> list[str]:
    return [bar.bar_id for bar in bars]
