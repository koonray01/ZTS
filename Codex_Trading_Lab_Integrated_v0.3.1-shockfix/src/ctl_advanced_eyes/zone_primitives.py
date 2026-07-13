from __future__ import annotations

from ctl_eyes.base import SensorOutputBuilder
from ctl_eyes.models import SensorContext

from .common import atr_like_reference, cluster_points, confirmed_swing_points, touches_zone, zone_id


def analyze_zone_primitives(context: SensorContext) -> dict:
    builder = SensorOutputBuilder(context, "zone_primitives", "0.1.0", "ZONE")
    if len(context.bars) < 12:
        builder.unknown("INSUFFICIENT_BARS_FOR_ZONES", "Need at least 12 closed bars.", True)
        return builder.build()

    reference = atr_like_reference(context.bars)
    if reference is None or reference <= 0:
        builder.unknown("NO_ZONE_VOLATILITY_REFERENCE", "Cannot derive zone tolerance.", True)
        return builder.build()

    highs, lows = confirmed_swing_points(context)
    points = [
        {**item, "origin_type": "SWING_HIGH"} for item in highs
    ] + [
        {**item, "origin_type": "SWING_LOW"} for item in lows
    ]
    tolerance = max(reference * 0.20, 1e-9)
    clusters = cluster_points(points, tolerance)

    zones = []
    latest = context.bars[-1]
    for index, cluster in enumerate(clusters, start=1):
        center = sum(float(item["level"]) for item in cluster) / len(cluster)
        lower = min(float(item["level"]) for item in cluster) - tolerance * 0.35
        upper = max(float(item["level"]) for item in cluster) + tolerance * 0.35
        evidence = list(dict.fromkeys(ref for item in cluster for ref in item["evidence_refs"]))
        origin_types = sorted(set(item["origin_type"] for item in cluster))
        touch_count = sum(1 for bar in context.bars if touches_zone(bar, lower, upper))
        interaction = touches_zone(latest, lower, upper)
        zone = {
            "zone_id": zone_id("ZONE", context.timeframe, index),
            "lower": lower,
            "upper": upper,
            "center": center,
            "origin_types": origin_types,
            "cluster_points": len(cluster),
            "touch_count": touch_count,
            "latest_interaction": interaction,
            "definition_version": "ZONE_CLUSTER_V0_1",
            "evidence_refs": evidence,
        }
        zones.append(zone)
        if interaction:
            builder.event(
                "ZONE_TOUCH",
                "CONFIRMED",
                "NOT_APPLICABLE",
                evidence + [latest.bar_id],
                band={"lower": lower, "upper": upper},
                first_seen_at=latest.close_time,
                confirmed_at=latest.close_time,
            )

    source_id = builder.fact(
        "zone_volatility_reference",
        reference,
        [bar.bar_id for bar in context.bars[-20:]],
        "price",
    )
    builder.derive(
        "zone_primitives",
        zones,
        "ZONE_CLUSTER_V0_1",
        [source_id],
        list(dict.fromkeys(ref for zone in zones for ref in zone["evidence_refs"])) or [context.bars[-1].bar_id],
    )
    if not zones:
        builder.unknown("NO_ZONE_PRIMITIVES", "No confirmed swing clusters formed zones.", False)
    return builder.build()
