from __future__ import annotations

from ctl_eyes.base import SensorOutputBuilder
from ctl_eyes.models import SensorContext
from ctl_eyes.utils import find_confirmed_swings


def _prior_structure(highs, lows) -> str:
    if len(highs) < 2 or len(lows) < 2:
        return "UNSCORABLE"
    high_state = "HH" if highs[-1]["level"] > highs[-2]["level"] else "LH"
    low_state = "HL" if lows[-1]["level"] > lows[-2]["level"] else "LL"
    if high_state == "HH" and low_state == "HL":
        return "BULLISH"
    if high_state == "LH" and low_state == "LL":
        return "BEARISH"
    return "TRANSITION"


def analyze_smc_structure(context: SensorContext) -> dict:
    builder = SensorOutputBuilder(context, "smc_structure_interpretation", "0.1.0", "STRUCTURE")
    bars = list(context.bars)
    if len(bars) < 10:
        builder.unknown("INSUFFICIENT_BARS_FOR_SMC", "Need at least 10 closed bars.", True)
        return builder.build()

    latest = bars[-1]
    historical = tuple(bars[:-1])
    highs, lows = find_confirmed_swings(historical)
    prior = _prior_structure(highs, lows)
    builder.derive(
        "prior_structure_state",
        prior,
        "PRIOR_STRUCTURE_FOR_SMC_V0_1",
        [bar.bar_id for bar in historical],
        [bar.bar_id for bar in historical],
    )

    events = []
    if highs:
        level = highs[-1]["level"]
        refs = list(dict.fromkeys(highs[-1]["evidence_refs"] + [latest.bar_id]))
        if latest.close > level:
            label = "BOS_BULLISH" if prior == "BULLISH" else "CHOCH_MSS_BULLISH_CANDIDATE"
            builder.event(
                "BREAK",
                "CONFIRMED",
                "BULLISH",
                refs,
                level=level,
                first_seen_at=latest.close_time,
                confirmed_at=latest.close_time,
                label=label,
            )
            events.append({"label": label, "level": level, "evidence_refs": refs})
        elif latest.high > level and latest.close <= level:
            events.append({"label": "HIGH_SWEEP_NO_BOS", "level": level, "evidence_refs": refs})

    if lows:
        level = lows[-1]["level"]
        refs = list(dict.fromkeys(lows[-1]["evidence_refs"] + [latest.bar_id]))
        if latest.close < level:
            label = "BOS_BEARISH" if prior == "BEARISH" else "CHOCH_MSS_BEARISH_CANDIDATE"
            builder.event(
                "BREAK",
                "CONFIRMED",
                "BEARISH",
                refs,
                level=level,
                first_seen_at=latest.close_time,
                confirmed_at=latest.close_time,
                label=label,
            )
            events.append({"label": label, "level": level, "evidence_refs": refs})
        elif latest.low < level and latest.close >= level:
            events.append({"label": "LOW_SWEEP_NO_BOS", "level": level, "evidence_refs": refs})

    builder.derive(
        "smc_structure_events",
        events,
        "SMC_STRUCTURE_INTERPRETATION_V0_1",
        [bar.bar_id for bar in bars],
        list(dict.fromkeys(ref for event in events for ref in event["evidence_refs"])) or [latest.bar_id],
    )
    if not events:
        builder.unknown("NO_SMC_STRUCTURE_EVENT", "No BOS/CHoCH/MSS candidate on latest closed bar.", False)
    return builder.build()
