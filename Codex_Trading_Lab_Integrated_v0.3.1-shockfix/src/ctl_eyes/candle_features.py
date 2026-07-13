from __future__ import annotations

from .base import SensorOutputBuilder
from .models import SensorContext
from .utils import median, safe_ratio, true_ranges


def analyze_candle_features(context: SensorContext) -> dict:
    builder = SensorOutputBuilder(context, "candle_features", "0.1.0", "FEATURE")
    if not context.bars:
        builder.unknown("NO_BARS", "No closed bars available.", True)
        return builder.build()

    latest = context.bars[-1]
    evidence = [latest.bar_id]
    bar_range = latest.high - latest.low
    body = abs(latest.close - latest.open)
    upper_wick = latest.high - max(latest.open, latest.close)
    lower_wick = min(latest.open, latest.close) - latest.low

    open_id = builder.fact("latest_open", latest.open, evidence, "price")
    high_id = builder.fact("latest_high", latest.high, evidence, "price")
    low_id = builder.fact("latest_low", latest.low, evidence, "price")
    close_id = builder.fact("latest_close", latest.close, evidence, "price")
    range_id = builder.fact("range_size", bar_range, evidence, "price")
    body_id = builder.fact("body_size", body, evidence, "price")
    upper_id = builder.fact("upper_wick_size", upper_wick, evidence, "price")
    lower_id = builder.fact("lower_wick_size", lower_wick, evidence, "price")

    direction = "BULLISH" if latest.close > latest.open else "BEARISH" if latest.close < latest.open else "NEUTRAL"
    builder.derive(
        "candle_direction",
        direction,
        "CANDLE_DIRECTION_V0_1",
        [open_id, close_id],
        evidence,
    )
    body_ratio = safe_ratio(body, bar_range)
    upper_ratio = safe_ratio(upper_wick, bar_range)
    lower_ratio = safe_ratio(lower_wick, bar_range)
    builder.derive("body_to_range", body_ratio, "BODY_RANGE_RATIO_V0_1", [body_id, range_id], evidence)
    builder.derive("upper_wick_ratio", upper_ratio, "WICK_RATIO_V0_1", [upper_id, range_id], evidence)
    builder.derive("lower_wick_ratio", lower_ratio, "WICK_RATIO_V0_1", [lower_id, range_id], evidence)

    trs = true_ranges(context.bars)
    reference = median(trs[:-1][-20:]) if len(trs) > 1 else None
    if reference is None or reference <= 0:
        builder.unknown("INSUFFICIENT_TR_HISTORY", "Cannot calculate a stable range baseline.", False)
    else:
        ref_id = builder.fact(
            "median_true_range_reference",
            reference,
            [bar.bar_id for bar in context.bars[max(0, len(context.bars) - 21):-1]],
            "price",
        )
        ratio = bar_range / reference
        ratio_id = builder.derive(
            "range_to_median_true_range",
            ratio,
            "RANGE_MEDIAN_TR_V0_1",
            [range_id, ref_id],
            [bar.bar_id for bar in context.bars[-21:]],
        )
        if ratio >= 2.0 and (body_ratio or 0.0) >= 0.65:
            builder.event(
                "DISPLACEMENT",
                "CONFIRMED",
                direction,
                [bar.bar_id for bar in context.bars[-21:]],
                closed_bar_confirmed=True,
                first_seen_at=latest.close_time,
                confirmed_at=latest.close_time,
            )

    return builder.build()
