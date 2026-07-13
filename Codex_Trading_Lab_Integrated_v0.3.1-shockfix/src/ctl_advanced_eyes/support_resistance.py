from __future__ import annotations

from ctl_eyes.base import SensorOutputBuilder
from ctl_eyes.models import SensorContext

from .common import atr_like_reference, cluster_points, confirmed_swing_points, touches_zone, zone_id


def analyze_support_resistance(context: SensorContext) -> dict:
    builder = SensorOutputBuilder(context, "support_resistance", "0.1.0", "ZONE")
    if len(context.bars) < 12:
        builder.unknown("INSUFFICIENT_BARS_FOR_SR", "Need at least 12 closed bars.", True)
        return builder.build()

    reference = atr_like_reference(context.bars)
    if not reference:
        builder.unknown("NO_SR_REFERENCE", "No valid volatility reference.", True)
        return builder.build()

    highs, lows = confirmed_swing_points(context)
    points = [{**item, "pivot": "HIGH"} for item in highs] + [{**item, "pivot": "LOW"} for item in lows]
    clusters = cluster_points(points, reference * 0.18)
    price = context.bars[-1].close
    zones = []

    for index, cluster in enumerate(clusters, start=1):
        center = sum(item["level"] for item in cluster) / len(cluster)
        half_width = reference * 0.10
        lower, upper = center - half_width, center + half_width
        if lower <= price <= upper:
            role = "ACTIVE_INTERACTION"
        elif upper < price:
            role = "SUPPORT_CANDIDATE"
        else:
            role = "RESISTANCE_CANDIDATE"

        evidence = list(dict.fromkeys(ref for item in cluster for ref in item["evidence_refs"]))
        pivot_mix = sorted(set(item["pivot"] for item in cluster))
        reaction_count = sum(1 for bar in context.bars if touches_zone(bar, lower, upper))
        zones.append(
            {
                "zone_id": zone_id("SR", context.timeframe, index),
                "lower": lower,
                "upper": upper,
                "role": role,
                "pivot_mix": pivot_mix,
                "cluster_points": len(cluster),
                "reaction_count": reaction_count,
                "definition_version": "SUPPORT_RESISTANCE_V0_1",
                "evidence_refs": evidence,
            }
        )

    builder.derive(
        "support_resistance_zones",
        zones,
        "SUPPORT_RESISTANCE_V0_1",
        [bar.bar_id for bar in context.bars[-20:]],
        list(dict.fromkeys(ref for zone in zones for ref in zone["evidence_refs"])) or [context.bars[-1].bar_id],
    )
    if not zones:
        builder.unknown("NO_SUPPORT_RESISTANCE_ZONE", "No S/R zone formed.", False)
    return builder.build()
