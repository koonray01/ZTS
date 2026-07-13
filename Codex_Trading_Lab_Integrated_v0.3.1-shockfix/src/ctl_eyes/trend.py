from __future__ import annotations

from .base import SensorOutputBuilder
from .models import SensorContext
from .utils import directional_efficiency, linear_regression_slope, median, true_ranges


def analyze_trend(context: SensorContext, lookback: int = 20) -> dict:
    builder = SensorOutputBuilder(context, "trend_state", "0.1.0", "TREND")
    bars = list(context.bars[-lookback:])
    if len(bars) < 8:
        builder.unknown("INSUFFICIENT_BARS_FOR_TREND", "Need at least 8 closed bars.", True)
        return builder.build()

    closes = [bar.close for bar in bars]
    evidence = [bar.bar_id for bar in bars]
    trs = true_ranges(bars)
    tr_median = median(trs)
    slope = linear_regression_slope(closes)
    normalized_slope = 0.0 if not tr_median else slope / tr_median
    efficiency = directional_efficiency(closes)

    start_id = builder.fact("trend_window_start_close", closes[0], [bars[0].bar_id], "price")
    end_id = builder.fact("trend_window_end_close", closes[-1], [bars[-1].bar_id], "price")
    tr_id = builder.fact("trend_window_median_true_range", tr_median, evidence, "price")
    slope_id = builder.derive(
        "normalized_regression_slope",
        normalized_slope,
        "NORMALIZED_LR_SLOPE_V0_1",
        [start_id, end_id, tr_id],
        evidence,
    )
    efficiency_id = builder.derive(
        "directional_efficiency",
        efficiency,
        "DIRECTIONAL_EFFICIENCY_V0_1",
        [start_id, end_id],
        evidence,
    )

    if normalized_slope >= 0.12 and efficiency >= 0.25:
        state = "BULLISH"
    elif normalized_slope <= -0.12 and efficiency >= 0.25:
        state = "BEARISH"
    elif abs(normalized_slope) < 0.08 and efficiency < 0.30:
        state = "NEUTRAL"
    else:
        state = "TRANSITION"

    magnitude = abs(normalized_slope) * max(efficiency, 0.01)
    strength = "STRONG" if magnitude >= 0.30 else "MODERATE" if magnitude >= 0.12 else "WEAK"

    state_id = builder.derive(
        "trend_state",
        state,
        "TREND_STATE_V0_1",
        [slope_id, efficiency_id],
        evidence,
    )
    builder.derive(
        "trend_strength",
        strength,
        "TREND_STRENGTH_V0_1",
        [state_id, slope_id, efficiency_id],
        evidence,
    )
    return builder.build()
