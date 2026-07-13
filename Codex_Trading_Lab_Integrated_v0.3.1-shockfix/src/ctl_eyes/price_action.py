from __future__ import annotations

from .base import SensorOutputBuilder
from .models import SensorContext
from .utils import find_confirmed_swings, median, ordered_structure_from_swings, safe_ratio, true_ranges


def analyze_price_action(context: SensorContext) -> dict:
    builder = SensorOutputBuilder(context, "basic_price_action", "0.1.0", "PRICE_ACTION")
    bars = list(context.bars)
    if len(bars) < 8:
        builder.unknown("INSUFFICIENT_BARS_FOR_PRICE_ACTION", "Need at least 8 closed bars.", True)
        return builder.build()

    latest = bars[-1]
    previous = bars[-2]
    highs, lows = find_confirmed_swings(tuple(bars[:-1]))
    prior_structure = ordered_structure_from_swings(highs, lows)["state"]
    latest_high = highs[-1] if highs else None
    latest_low = lows[-1] if lows else None

    if latest_high is None and latest_low is None:
        builder.unknown("NO_REFERENCE_SWINGS", "No confirmed swing reference before latest bar.", True)
        return builder.build()

    latest_range = latest.high - latest.low
    body = abs(latest.close - latest.open)
    upper_wick = latest.high - max(latest.open, latest.close)
    lower_wick = min(latest.open, latest.close) - latest.low
    upper_ratio = safe_ratio(upper_wick, latest_range) or 0.0
    lower_ratio = safe_ratio(lower_wick, latest_range) or 0.0

    evidence_latest = [previous.bar_id, latest.bar_id]

    if latest_high is not None:
        level = latest_high["level"]
        refs = list(dict.fromkeys(latest_high["evidence_refs"] + evidence_latest))
        level_id = builder.fact("reference_swing_high", level, latest_high["evidence_refs"], "price")
        if latest.close > level:
            builder.event(
                "BREAK",
                "CONFIRMED",
                "BULLISH",
                refs,
                level=level,
                first_seen_at=latest.close_time,
                confirmed_at=latest.close_time,
                label="BOS_BULLISH" if prior_structure == "BULLISH" else "CHOCH_MSS_BULLISH_CANDIDATE",
            )
        elif latest.high > level and latest.close <= level:
            builder.event(
                "SWEEP",
                "CONFIRMED",
                "BEARISH",
                refs,
                level=level,
                first_seen_at=latest.close_time,
                confirmed_at=latest.close_time,
            )
        if previous.close > level and latest.close <= level:
            builder.event(
                "RECLAIM",
                "CONFIRMED",
                "BEARISH",
                refs,
                level=level,
                first_seen_at=latest.close_time,
                confirmed_at=latest.close_time,
            )

    if latest_low is not None:
        level = latest_low["level"]
        refs = list(dict.fromkeys(latest_low["evidence_refs"] + evidence_latest))
        level_id = builder.fact("reference_swing_low", level, latest_low["evidence_refs"], "price")
        if latest.close < level:
            builder.event(
                "BREAK",
                "CONFIRMED",
                "BEARISH",
                refs,
                level=level,
                first_seen_at=latest.close_time,
                confirmed_at=latest.close_time,
                label="BOS_BEARISH" if prior_structure == "BEARISH" else "CHOCH_MSS_BEARISH_CANDIDATE",
            )
        elif latest.low < level and latest.close >= level:
            builder.event(
                "SWEEP",
                "CONFIRMED",
                "BULLISH",
                refs,
                level=level,
                first_seen_at=latest.close_time,
                confirmed_at=latest.close_time,
            )
        if previous.close < level and latest.close >= level:
            builder.event(
                "RECLAIM",
                "CONFIRMED",
                "BULLISH",
                refs,
                level=level,
                first_seen_at=latest.close_time,
                confirmed_at=latest.close_time,
            )

    midpoint = (latest.high + latest.low) / 2.0
    if lower_ratio >= 0.55 and latest.close >= midpoint:
        builder.event(
            "REJECTION",
            "CONFIRMED",
            "BULLISH",
            [latest.bar_id],
            first_seen_at=latest.close_time,
            confirmed_at=latest.close_time,
        )
    if upper_ratio >= 0.55 and latest.close <= midpoint:
        builder.event(
            "REJECTION",
            "CONFIRMED",
            "BEARISH",
            [latest.bar_id],
            first_seen_at=latest.close_time,
            confirmed_at=latest.close_time,
        )

    trs = true_ranges(tuple(bars))
    reference = median(trs[:-1][-20:])
    if reference and reference > 0:
        tr_ratio = trs[-1] / reference
        body_ratio = safe_ratio(body, latest_range) or 0.0
        if tr_ratio >= 2.0 and body_ratio >= 0.65:
            direction = "BULLISH" if latest.close > latest.open else "BEARISH" if latest.close < latest.open else "NEUTRAL"
            builder.event(
                "DISPLACEMENT",
                "CONFIRMED",
                direction,
                [bar.bar_id for bar in bars[-21:]],
                first_seen_at=latest.close_time,
                confirmed_at=latest.close_time,
            )

    if not builder.events:
        builder.unknown("NO_CONFIRMED_PRICE_ACTION_EVENT", "No basic event confirmed on latest closed bar.", False)

    return builder.build()
