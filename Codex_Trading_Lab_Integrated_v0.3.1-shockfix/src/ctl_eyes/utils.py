from __future__ import annotations

import math
import statistics
from collections.abc import Iterable
from typing import Any

from .models import Bar


def true_range(bar: Bar, previous_close: float | None) -> float:
    if previous_close is None:
        return bar.high - bar.low
    return max(
        bar.high - bar.low,
        abs(bar.high - previous_close),
        abs(bar.low - previous_close),
    )


def true_ranges(bars: Iterable[Bar]) -> list[float]:
    result: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        result.append(true_range(bar, previous_close))
        previous_close = bar.close
    return result


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def median(values: Iterable[float]) -> float | None:
    seq = list(values)
    if not seq:
        return None
    return float(statistics.median(seq))


def linear_regression_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    return 0.0 if denominator == 0 else numerator / denominator


def directional_efficiency(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    path = sum(abs(values[i] - values[i - 1]) for i in range(1, len(values)))
    if path == 0:
        return 0.0
    return abs(values[-1] - values[0]) / path


def average_overlap_ratio(bars: list[Bar]) -> float:
    if len(bars) < 2:
        return 0.0
    ratios: list[float] = []
    for previous, current in zip(bars, bars[1:]):
        overlap = max(0.0, min(previous.high, current.high) - max(previous.low, current.low))
        smaller_range = min(previous.high - previous.low, current.high - current.low)
        ratios.append(0.0 if smaller_range <= 0 else min(1.0, overlap / smaller_range))
    return sum(ratios) / len(ratios)


def ensure_closed_valid_bars(bars: tuple[Bar, ...]) -> list[str]:
    errors: list[str] = []
    previous_close_time: str | None = None
    for bar in bars:
        if not bar.is_closed:
            errors.append(f"OPEN_BAR:{bar.bar_id}")
        if bar.high < bar.low:
            errors.append(f"INVALID_HIGH_LOW:{bar.bar_id}")
        if not (bar.low <= bar.open <= bar.high):
            errors.append(f"OPEN_OUTSIDE_RANGE:{bar.bar_id}")
        if not (bar.low <= bar.close <= bar.high):
            errors.append(f"CLOSE_OUTSIDE_RANGE:{bar.bar_id}")
        if bar.tick_volume < 0:
            errors.append(f"NEGATIVE_VOLUME:{bar.bar_id}")
        if previous_close_time is not None and bar.close_time <= previous_close_time:
            errors.append(f"NON_MONOTONIC_TIME:{bar.bar_id}")
        previous_close_time = bar.close_time
    return errors


def latest_evidence(bars: tuple[Bar, ...], count: int = 1) -> list[str]:
    return [bar.bar_id for bar in bars[-count:]]


def sanitize_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value.upper())
    cleaned = cleaned.strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"X_{cleaned}"
    return cleaned[:127]


def find_confirmed_swings(
    bars: tuple[Bar, ...],
    left: int = 2,
    right: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    highs: list[dict[str, Any]] = []
    lows: list[dict[str, Any]] = []
    if len(bars) < left + right + 1:
        return highs, lows

    for index in range(left, len(bars) - right):
        center = bars[index]
        left_bars = bars[index - left:index]
        right_bars = bars[index + 1:index + right + 1]
        neighbors = left_bars + right_bars

        if all(center.high > bar.high for bar in neighbors):
            highs.append(
                {
                    "index": index,
                    "level": center.high,
                    "bar": center,
                    "confirmed_by": bars[index + right],
                    "evidence_refs": [bar.bar_id for bar in bars[index - left:index + right + 1]],
                }
            )
        if all(center.low < bar.low for bar in neighbors):
            lows.append(
                {
                    "index": index,
                    "level": center.low,
                    "bar": center,
                    "confirmed_by": bars[index + right],
                    "evidence_refs": [bar.bar_id for bar in bars[index - left:index + right + 1]],
                }
            )
    return highs, lows


def ordered_structure_from_swings(
    highs: list[dict[str, Any]],
    lows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify swings only after preserving their temporal alternation.

    Consecutive highs/lows are collapsed to the more extreme pivot.  This
    prevents the old independent-high/independent-low comparison from pairing
    pivots that never formed a usable market-structure sequence.
    """
    raw = sorted(
        [{"kind": "HIGH", **item} for item in highs] + [{"kind": "LOW", **item} for item in lows],
        key=lambda item: item["index"],
    )
    alternating: list[dict[str, Any]] = []
    for pivot in raw:
        if not alternating or alternating[-1]["kind"] != pivot["kind"]:
            alternating.append(pivot)
            continue
        prior = alternating[-1]
        is_more_extreme = pivot["level"] > prior["level"] if pivot["kind"] == "HIGH" else pivot["level"] < prior["level"]
        if is_more_extreme:
            alternating[-1] = pivot

    sequence_highs = [pivot for pivot in alternating if pivot["kind"] == "HIGH"]
    sequence_lows = [pivot for pivot in alternating if pivot["kind"] == "LOW"]
    if len(sequence_highs) < 2 or len(sequence_lows) < 2:
        return {"state": "UNKNOWN", "high_sequence": None, "low_sequence": None, "pivots": alternating}

    high_sequence = "HH" if sequence_highs[-1]["level"] > sequence_highs[-2]["level"] else "LH" if sequence_highs[-1]["level"] < sequence_highs[-2]["level"] else "EH"
    low_sequence = "HL" if sequence_lows[-1]["level"] > sequence_lows[-2]["level"] else "LL" if sequence_lows[-1]["level"] < sequence_lows[-2]["level"] else "EL"
    if high_sequence == "HH" and low_sequence == "HL":
        state = "BULLISH"
    elif high_sequence == "LH" and low_sequence == "LL":
        state = "BEARISH"
    elif high_sequence in {"EH", "LH"} and low_sequence in {"EL", "HL"}:
        state = "RANGE_OR_COMPRESSION"
    else:
        state = "TRANSITION"
    return {"state": state, "high_sequence": high_sequence, "low_sequence": low_sequence, "pivots": alternating}
