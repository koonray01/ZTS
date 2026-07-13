from __future__ import annotations

from .base import SensorOutputBuilder
from .models import SensorContext
from .utils import find_confirmed_swings


def analyze_swings(context: SensorContext, left: int = 2, right: int = 2) -> dict:
    builder = SensorOutputBuilder(context, "confirmed_swings", "0.1.0", "STRUCTURE")
    highs, lows = find_confirmed_swings(context.bars, left=left, right=right)

    if len(context.bars) < left + right + 1:
        builder.unknown(
            "INSUFFICIENT_BARS_FOR_SWINGS",
            f"Need at least {left + right + 1} closed bars.",
            True,
        )
        return builder.build()

    if highs:
        latest = highs[-1]
        high_id = builder.fact(
            "latest_confirmed_swing_high",
            latest["level"],
            latest["evidence_refs"],
            "price",
        )
        builder.derive(
            "confirmed_swing_high_count",
            len(highs),
            "FRACTAL_SWING_COUNT_V0_1",
            [high_id],
            [ref for swing in highs for ref in swing["evidence_refs"]],
        )
    else:
        builder.unknown("NO_CONFIRMED_SWING_HIGH", "No confirmed swing high in the window.", False)

    if lows:
        latest = lows[-1]
        low_id = builder.fact(
            "latest_confirmed_swing_low",
            latest["level"],
            latest["evidence_refs"],
            "price",
        )
        builder.derive(
            "confirmed_swing_low_count",
            len(lows),
            "FRACTAL_SWING_COUNT_V0_1",
            [low_id],
            [ref for swing in lows for ref in swing["evidence_refs"]],
        )
    else:
        builder.unknown("NO_CONFIRMED_SWING_LOW", "No confirmed swing low in the window.", False)

    combined = sorted(
        [("SWING_HIGH", item) for item in highs] + [("SWING_LOW", item) for item in lows],
        key=lambda value: value[1]["index"],
    )[-8:]
    for event_type, item in combined:
        builder.event(
            event_type,
            "CONFIRMED",
            "NOT_APPLICABLE",
            item["evidence_refs"],
            level=item["level"],
            closed_bar_confirmed=True,
            first_seen_at=item["confirmed_by"].close_time,
            confirmed_at=item["confirmed_by"].close_time,
        )

    return builder.build()
