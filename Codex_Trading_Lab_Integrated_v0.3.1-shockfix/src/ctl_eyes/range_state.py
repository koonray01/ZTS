from __future__ import annotations

from .base import SensorOutputBuilder
from .models import SensorContext
from .utils import average_overlap_ratio, directional_efficiency, true_ranges


def analyze_range_state(context: SensorContext, lookback: int = 20) -> dict:
    builder = SensorOutputBuilder(context, "range_state", "0.1.0", "RANGE")
    bars = list(context.bars[-lookback:])
    if len(bars) < 8:
        builder.unknown("INSUFFICIENT_BARS_FOR_RANGE", "Need at least 8 closed bars.", True)
        return builder.build()

    closes = [bar.close for bar in bars]
    evidence = [bar.bar_id for bar in bars]
    efficiency = directional_efficiency(closes)
    overlap = average_overlap_ratio(bars)
    total_path = sum(true_ranges(bars))
    envelope_width = max(bar.high for bar in bars) - min(bar.low for bar in bars)
    path_ratio = 0.0 if total_path <= 0 else envelope_width / total_path

    efficiency_id = builder.derive(
        "directional_efficiency",
        efficiency,
        "RANGE_DIRECTIONAL_EFFICIENCY_V0_1",
        evidence,
        evidence,
    )
    overlap_id = builder.derive(
        "average_bar_overlap_ratio",
        overlap,
        "BAR_OVERLAP_V0_1",
        evidence,
        evidence,
    )
    path_id = builder.derive(
        "envelope_to_total_path_ratio",
        path_ratio,
        "RANGE_PATH_RATIO_V0_1",
        evidence,
        evidence,
    )

    if efficiency <= 0.25 and overlap >= 0.45 and path_ratio <= 0.35:
        state = "RANGE"
    elif efficiency >= 0.45 and path_ratio >= 0.35:
        state = "TRENDING"
    else:
        state = "TRANSITION"

    builder.derive(
        "range_state",
        state,
        "RANGE_STATE_V0_1",
        [efficiency_id, overlap_id, path_id],
        evidence,
    )
    return builder.build()
