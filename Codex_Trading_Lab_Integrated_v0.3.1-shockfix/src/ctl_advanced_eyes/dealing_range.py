from __future__ import annotations

from ctl_eyes.base import SensorOutputBuilder
from ctl_eyes.models import SensorContext
from ctl_eyes.utils import find_confirmed_swings


def analyze_dealing_range(context: SensorContext) -> dict:
    builder = SensorOutputBuilder(context, "dealing_range", "0.1.0", "CONTEXT")
    if len(context.bars) < 10:
        builder.unknown("INSUFFICIENT_BARS_FOR_DEALING_RANGE", "Need at least 10 closed bars.", True)
        return builder.build()

    highs, lows = find_confirmed_swings(context.bars)
    if not highs or not lows:
        builder.status = "UNSCORABLE"
        builder.unknown("NO_CONFIRMED_RANGE_BOUNDARIES", "Need a confirmed swing high and low.", True)
        return builder.build()

    high = highs[-1]
    low = lows[-1]
    upper = high["level"]
    lower = low["level"]
    if upper <= lower:
        builder.status = "UNSCORABLE"
        builder.unknown("INVALID_DEALING_RANGE", "Swing high is not above swing low.", True)
        return builder.build()

    equilibrium = (upper + lower) / 2.0
    close = context.bars[-1].close
    if close > equilibrium:
        location = "PREMIUM"
    elif close < equilibrium:
        location = "DISCOUNT"
    else:
        location = "EQUILIBRIUM"

    evidence = list(dict.fromkeys(high["evidence_refs"] + low["evidence_refs"] + [context.bars[-1].bar_id]))
    high_id = builder.fact("dealing_range_high", upper, high["evidence_refs"], "price")
    low_id = builder.fact("dealing_range_low", lower, low["evidence_refs"], "price")
    eq_id = builder.derive(
        "dealing_range_equilibrium",
        equilibrium,
        "DEALING_RANGE_50_V0_1",
        [high_id, low_id],
        evidence,
    )
    builder.derive(
        "dealing_range_location",
        location,
        "PREMIUM_DISCOUNT_LOCATION_V0_1",
        [eq_id, context.bars[-1].bar_id],
        evidence,
    )
    return builder.build()
