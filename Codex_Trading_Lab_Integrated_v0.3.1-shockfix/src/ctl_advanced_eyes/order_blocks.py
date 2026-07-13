from __future__ import annotations

from ctl_eyes.base import SensorOutputBuilder
from ctl_eyes.models import SensorContext
from ctl_eyes.utils import find_confirmed_swings, median, true_ranges


def analyze_order_block_candidates(context: SensorContext) -> dict:
    builder = SensorOutputBuilder(context, "order_block_candidates", "0.1.0", "ZONE")
    bars = list(context.bars)
    if len(bars) < 12:
        builder.unknown("INSUFFICIENT_BARS_FOR_OB", "Need at least 12 closed bars.", True)
        return builder.build()

    latest = bars[-1]
    historical = tuple(bars[:-1])
    highs, lows = find_confirmed_swings(historical)
    trs = true_ranges(tuple(bars))
    reference = median(trs[:-1][-20:])
    if not reference:
        builder.unknown("NO_OB_VOLATILITY_REFERENCE", "No volatility reference.", True)
        return builder.build()

    candidates = []
    breaks = []
    if highs and latest.close > highs[-1]["level"]:
        breaks.append(("BULLISH", highs[-1]["level"], highs[-1]["evidence_refs"]))
    if lows and latest.close < lows[-1]["level"]:
        breaks.append(("BEARISH", lows[-1]["level"], lows[-1]["evidence_refs"]))

    latest_body = abs(latest.close - latest.open)
    displacement = (latest.high - latest.low) >= reference * 1.8 and latest_body >= (latest.high - latest.low) * 0.60

    if displacement:
        for direction, break_level, break_refs in breaks:
            opposite = []
            for bar in reversed(bars[-7:-1]):
                if direction == "BULLISH" and bar.close < bar.open:
                    opposite.append(bar)
                    break
                if direction == "BEARISH" and bar.close > bar.open:
                    opposite.append(bar)
                    break
            if not opposite:
                continue
            origin = opposite[0]
            if direction == "BULLISH":
                lower, upper = origin.low, origin.open
                kind = "BULLISH_ORDER_BLOCK_CANDIDATE"
            else:
                lower, upper = origin.open, origin.high
                kind = "BEARISH_ORDER_BLOCK_CANDIDATE"
            evidence = list(dict.fromkeys([origin.bar_id, latest.bar_id] + break_refs))
            candidates.append(
                {
                    "candidate_id": f"OB_{context.timeframe}_{len(candidates) + 1:03d}",
                    "kind": kind,
                    "direction": direction,
                    "lower": lower,
                    "upper": upper,
                    "origin_bar_id": origin.bar_id,
                    "break_level": break_level,
                    "available_at": latest.close_time,
                    "interpretation_status": "CANDIDATE_NOT_INSTITUTIONAL_PROOF",
                    "definition_version": "ORDER_BLOCK_CANDIDATE_V0_1",
                    "evidence_refs": evidence,
                }
            )

    builder.derive(
        "order_block_candidates",
        candidates,
        "ORDER_BLOCK_CANDIDATE_V0_1",
        [bar.bar_id for bar in bars],
        list(dict.fromkeys(ref for item in candidates for ref in item["evidence_refs"])) or [latest.bar_id],
    )
    if not candidates:
        builder.unknown("NO_ORDER_BLOCK_CANDIDATE", "No displacement-break order-block candidate.", False)
    return builder.build()
