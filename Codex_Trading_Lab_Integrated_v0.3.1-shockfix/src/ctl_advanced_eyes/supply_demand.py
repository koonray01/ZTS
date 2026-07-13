from __future__ import annotations

from ctl_eyes.base import SensorOutputBuilder
from ctl_eyes.models import SensorContext
from ctl_eyes.utils import median, true_ranges

from .common import touches_zone, zone_id


def analyze_supply_demand(context: SensorContext) -> dict:
    builder = SensorOutputBuilder(context, "supply_demand_candidates", "0.1.0", "ZONE")
    bars = list(context.bars)
    if len(bars) < 12:
        builder.unknown("INSUFFICIENT_BARS_FOR_SD", "Need at least 12 closed bars.", True)
        return builder.build()

    trs = true_ranges(bars)
    candidates = []
    for index in range(5, len(bars) - 2):
        base = bars[index]
        reference = median(trs[max(0, index - 10):index])
        if not reference or reference <= 0:
            continue
        base_range = base.high - base.low
        if base_range > reference * 0.85:
            continue

        forward = bars[index + 1:index + 4]
        bullish_move = max(bar.high for bar in forward) - base.high
        bearish_move = base.low - min(bar.low for bar in forward)
        direction = None
        if bullish_move >= reference * 1.7 and bullish_move > bearish_move * 1.2:
            direction = "BULLISH"
            lower = base.low
            upper = max(base.open, base.close)
            kind = "DEMAND_CANDIDATE"
        elif bearish_move >= reference * 1.7 and bearish_move > bullish_move * 1.2:
            direction = "BEARISH"
            lower = min(base.open, base.close)
            upper = base.high
            kind = "SUPPLY_CANDIDATE"
        else:
            continue

        subsequent = bars[index + 4:]
        touch_count = sum(1 for bar in subsequent if touches_zone(bar, lower, upper))
        invalidated = any(
            bar.close < lower if direction == "BULLISH" else bar.close > upper
            for bar in subsequent
        )
        evidence = [base.bar_id] + [bar.bar_id for bar in forward]
        candidates.append(
            {
                "zone_id": zone_id("SD", context.timeframe, len(candidates) + 1),
                "kind": kind,
                "direction": direction,
                "lower": lower,
                "upper": upper,
                "base_bar_id": base.bar_id,
                "available_at": forward[-1].close_time,
                "departure_multiple": max(bullish_move, bearish_move) / reference,
                "subsequent_touch_count": touch_count,
                "invalidated": invalidated,
                "status": "INVALIDATED" if invalidated else "ACTIVE_CANDIDATE",
                "definition_version": "SUPPLY_DEMAND_BASE_DEPARTURE_V0_1",
                "evidence_refs": evidence,
            }
        )

    builder.derive(
        "supply_demand_candidates",
        candidates,
        "SUPPLY_DEMAND_BASE_DEPARTURE_V0_1",
        [bar.bar_id for bar in bars],
        list(dict.fromkeys(ref for item in candidates for ref in item["evidence_refs"])) or [bars[-1].bar_id],
    )
    if not candidates:
        builder.unknown("NO_SUPPLY_DEMAND_CANDIDATE", "No base-departure candidate found.", False)
    return builder.build()
