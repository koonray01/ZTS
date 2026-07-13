from __future__ import annotations

from .base import SensorOutputBuilder
from .models import SensorContext
from .utils import median, safe_ratio, true_ranges


def analyze_volatility(context: SensorContext, lookback: int = 20) -> dict:
    builder = SensorOutputBuilder(context, "volatility_shock", "0.1.0", "VOLATILITY")
    bars = list(context.bars)
    if len(bars) < 6:
        builder.unknown("INSUFFICIENT_BARS_FOR_VOLATILITY", "Need at least 6 closed bars.", True)
        return builder.build()

    latest = bars[-1]
    evidence = [bar.bar_id for bar in bars[-(lookback + 1):]]
    trs = true_ranges(bars[-(lookback + 1):])
    latest_tr = trs[-1]
    reference = median(trs[:-1])
    body = abs(latest.close - latest.open)
    body_ratio = safe_ratio(body, latest.high - latest.low) or 0.0

    tr_id = builder.fact("latest_true_range", latest_tr, [latest.bar_id], "price")
    ref_id = builder.fact("rolling_median_true_range", reference, evidence[:-1], "price")

    if reference is None or reference <= 0:
        builder.unknown("NO_VOLATILITY_BASELINE", "No valid rolling true-range baseline.", True)
        return builder.build()

    ratio = latest_tr / reference
    ratio_id = builder.derive(
        "true_range_ratio",
        ratio,
        "TR_MEDIAN_RATIO_V0_1",
        [tr_id, ref_id],
        evidence,
    )
    body_id = builder.derive(
        "body_dominance_ratio",
        body_ratio,
        "BODY_DOMINANCE_V0_1",
        [latest.bar_id],
        [latest.bar_id],
    )

    shock = ratio >= 3.0 or (ratio >= 2.0 and body_ratio >= 0.70)
    elevated = ratio >= 1.8
    state = "SHOCK" if shock else "ELEVATED" if elevated else "NORMAL"
    state_id = builder.derive(
        "volatility_state",
        state,
        "VOLATILITY_STATE_V0_1",
        [ratio_id, body_id],
        evidence,
    )
    if shock:
        direction = "BULLISH" if latest.close > latest.open else "BEARISH" if latest.close < latest.open else "NEUTRAL"
        builder.event(
            "SHOCK",
            "CONFIRMED",
            direction,
            evidence,
            closed_bar_confirmed=True,
            first_seen_at=latest.close_time,
            confirmed_at=latest.close_time,
        )
    return builder.build()
