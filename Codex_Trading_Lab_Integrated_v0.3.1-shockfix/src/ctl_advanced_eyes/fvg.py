from __future__ import annotations

from ctl_eyes.base import SensorOutputBuilder
from ctl_eyes.models import SensorContext


def analyze_fair_value_gaps(context: SensorContext) -> dict:
    builder = SensorOutputBuilder(context, "fair_value_gap", "0.1.0", "PRICE_ACTION")
    bars = list(context.bars)
    if len(bars) < 3:
        builder.unknown("INSUFFICIENT_BARS_FOR_FVG", "Need at least three closed bars.", True)
        return builder.build()

    gaps = []
    for index in range(2, len(bars)):
        first, middle, third = bars[index - 2], bars[index - 1], bars[index]
        if third.low > first.high:
            lower, upper, direction = first.high, third.low, "BULLISH"
        elif third.high < first.low:
            lower, upper, direction = third.high, first.low, "BEARISH"
        else:
            continue

        future = bars[index + 1:]
        if direction == "BULLISH":
            fully_mitigated = any(bar.low <= lower for bar in future)
            touched = any(bar.low <= upper for bar in future)
        else:
            fully_mitigated = any(bar.high >= upper for bar in future)
            touched = any(bar.high >= lower for bar in future)

        gaps.append(
            {
                "gap_id": f"FVG_{context.timeframe}_{len(gaps) + 1:03d}",
                "direction": direction,
                "lower": lower,
                "upper": upper,
                "origin_bar_ids": [first.bar_id, middle.bar_id, third.bar_id],
                "available_at": third.close_time,
                "touched": touched,
                "fully_mitigated": fully_mitigated,
                "status": "MITIGATED" if fully_mitigated else "ACTIVE",
                "definition_version": "THREE_CANDLE_FVG_V0_1",
                "evidence_refs": [first.bar_id, middle.bar_id, third.bar_id],
            }
        )

    builder.derive(
        "fair_value_gaps",
        gaps,
        "THREE_CANDLE_FVG_V0_1",
        [bar.bar_id for bar in bars],
        list(dict.fromkeys(ref for gap in gaps for ref in gap["evidence_refs"])) or [bars[-1].bar_id],
    )
    if not gaps:
        builder.unknown("NO_FVG", "No three-candle fair value gap found.", False)
    return builder.build()
