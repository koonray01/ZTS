from __future__ import annotations

from ctl_eyes.base import SensorOutputBuilder
from ctl_eyes.models import SensorContext

from .common import atr_like_reference, cluster_points, confirmed_swing_points, zone_id


def analyze_liquidity_map(context: SensorContext) -> dict:
    builder = SensorOutputBuilder(context, "liquidity_map", "0.1.0", "LIQUIDITY")
    if len(context.bars) < 12:
        builder.unknown("INSUFFICIENT_BARS_FOR_LIQUIDITY", "Need at least 12 closed bars.", True)
        return builder.build()

    reference = atr_like_reference(context.bars)
    if not reference:
        builder.unknown("NO_LIQUIDITY_REFERENCE", "No volatility reference.", True)
        return builder.build()

    highs, lows = confirmed_swing_points(context)
    pools = []
    for label, direction, points in [
        ("EQUAL_HIGHS", "BEARISH", highs),
        ("EQUAL_LOWS", "BULLISH", lows),
    ]:
        for cluster in cluster_points(points, reference * 0.12):
            if len(cluster) < 2:
                continue
            center = sum(item["level"] for item in cluster) / len(cluster)
            lower = min(item["level"] for item in cluster) - reference * 0.05
            upper = max(item["level"] for item in cluster) + reference * 0.05
            evidence = list(dict.fromkeys(ref for item in cluster for ref in item["evidence_refs"]))
            pools.append(
                {
                    "pool_id": zone_id("LIQ", context.timeframe, len(pools) + 1),
                    "type": label,
                    "directional_implication": direction,
                    "lower": lower,
                    "upper": upper,
                    "center": center,
                    "source_count": len(cluster),
                    "definition_version": "EQUAL_SWING_LIQUIDITY_V0_1",
                    "evidence_refs": evidence,
                }
            )

    builder.derive(
        "liquidity_pools",
        pools,
        "EQUAL_SWING_LIQUIDITY_V0_1",
        [bar.bar_id for bar in context.bars],
        list(dict.fromkeys(ref for pool in pools for ref in pool["evidence_refs"])) or [context.bars[-1].bar_id],
    )
    if not pools:
        builder.unknown("NO_EQUAL_SWING_LIQUIDITY", "No equal-high/equal-low pool found.", False)
    return builder.build()
