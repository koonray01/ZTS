from __future__ import annotations

from typing import Any

from .helpers import (
    all_events,
    evidence_union,
    item_named,
    results_by_sensor,
    sanitize_id,
    semantic_id,
)


WORKING_ZONE_LIMITS = {"M5": 8, "M15": 8, "H1": 6, "H4": 6}


def _map_structure(value: Any, trend: Any, range_state: Any) -> str:
    if value in {"BULLISH", "BEARISH", "TRANSITION"}:
        return value
    if value == "RANGE_OR_COMPRESSION" or range_state == "RANGE":
        return "RANGE"
    if trend in {"BULLISH", "BEARISH"}:
        return trend
    if range_state == "TRANSITION":
        return "TRANSITION"
    return "UNKNOWN"


def _structure_value(result: dict[str, Any] | None) -> Any:
    """Prefer ordered swing structure; conflicting scales explicitly mean transition."""
    by_scale = item_named(result, "structure_by_scale")
    if isinstance(by_scale, dict):
        directional = {value for value in by_scale.values() if value in {"BULLISH", "BEARISH"}}
        if len(directional) > 1:
            return "TRANSITION"
        swing = by_scale.get("SWING")
        if swing and swing != "UNKNOWN":
            return swing
        internal = by_scale.get("INTERNAL")
        if internal and internal != "UNKNOWN":
            return internal
    return item_named(result, "structure_state")


def _map_phase(
    structure: str,
    range_state: Any,
    volatility: Any,
    candle_direction: Any,
    events: list[str],
    recent_leg: str,
) -> str:
    if volatility == "SHOCK":
        return "EXPANSION"
    if "DISPLACEMENT" in events:
        return "IMPULSE"
    if recent_leg == "COMPRESSION":
        return "COMPRESSION"
    if recent_leg.endswith("PULLBACK"):
        return "PULLBACK"
    if recent_leg.endswith("IMPULSE") or recent_leg.endswith("ROTATION"):
        return "IMPULSE"
    if range_state == "TRANSITION":
        return "COMPRESSION"
    if structure == "BULLISH" and candle_direction == "BEARISH":
        return "PULLBACK"
    if structure == "BEARISH" and candle_direction == "BULLISH":
        return "PULLBACK"
    if structure in {"BULLISH", "BEARISH"}:
        return "IMPULSE"
    return "UNKNOWN"


def _map_regime(structure: str, range_state: Any, trend: Any) -> str:
    if range_state == "RANGE" or structure == "RANGE":
        return "RANGE"
    if structure == "TRANSITION" or trend in {"TRANSITION", "NEUTRAL"}:
        return "TRANSITION"
    if structure in {"BULLISH", "BEARISH"}:
        return "TREND"
    return "UNKNOWN"


def _recent_leg(timeframe_data: dict[str, Any], structure: str, range_state: Any) -> str:
    bars = timeframe_data["bars"]
    if len(bars) < 4:
        return "UNKNOWN"
    recent = bars[-4:]
    move = float(recent[-1]["close"]) - float(recent[0]["close"])
    average_range = sum(float(bar["high"]) - float(bar["low"]) for bar in recent) / len(recent)
    if abs(move) <= max(average_range * 0.5, 0.01):
        return "COMPRESSION"
    direction = "BULLISH" if move > 0 else "BEARISH"
    if range_state == "RANGE" or structure == "RANGE":
        return f"{direction}_ROTATION"
    if structure == direction:
        return f"{direction}_IMPULSE"
    if structure in {"BULLISH", "BEARISH"}:
        return f"{direction}_PULLBACK"
    return f"{direction}_ROTATION"


def _map_volatility(value: Any) -> str:
    return {
        "SHOCK": "SHOCK",
        "ELEVATED": "HIGH",
        "NORMAL": "NORMAL",
    }.get(value, "UNKNOWN")


def _zone_from_sr(zone: dict[str, Any], timeframe: str) -> dict[str, Any]:
    role = zone["role"]
    if role == "SUPPORT_CANDIDATE":
        zone_type = "SUPPORT"
    elif role == "RESISTANCE_CANDIDATE":
        zone_type = "RESISTANCE"
    else:
        zone_type = "OTHER"
    touches = int(zone.get("reaction_count", 0))
    freshness = "FRESH" if touches <= 2 else "USED" if touches <= 4 else "HEAVILY_USED"
    return {
        "zone_id": semantic_id("ZONE", timeframe, zone_type, float(zone["lower"]), float(zone["upper"])),
        "timeframe": timeframe,
        "zone_type": zone_type,
        "lower": float(zone["lower"]),
        "upper": float(zone["upper"]),
        "status": "TOUCHED" if role == "ACTIVE_INTERACTION" else "ACTIVE",
        "freshness": freshness,
        "source_type": "SUPPORT_RESISTANCE",
        "evidence_refs": evidence_union(zone) or [sanitize_id(zone["zone_id"])],
    }


def _zone_from_sd(zone: dict[str, Any], timeframe: str) -> dict[str, Any]:
    zone_type = "DEMAND" if zone["kind"] == "DEMAND_CANDIDATE" else "SUPPLY"
    touches = int(zone.get("subsequent_touch_count", 0))
    freshness = "FRESH" if touches == 0 else "USED" if touches <= 2 else "HEAVILY_USED"
    return {
        "zone_id": semantic_id("ZONE", timeframe, zone_type, float(zone["lower"]), float(zone["upper"])),
        "timeframe": timeframe,
        "zone_type": zone_type,
        "lower": float(zone["lower"]),
        "upper": float(zone["upper"]),
        "status": "INVALIDATED" if zone["invalidated"] else "TOUCHED" if touches > 0 else "ACTIVE",
        "freshness": freshness,
        "available_at": zone.get("available_at"),
        "source_type": "SUPPLY_DEMAND",
        "evidence_refs": evidence_union(zone) or [sanitize_id(zone["zone_id"])],
    }


def _zone_from_fvg(gap: dict[str, Any], timeframe: str) -> dict[str, Any]:
    zone_type = "DEMAND" if gap["direction"] == "BULLISH" else "SUPPLY"
    return {
        "zone_id": semantic_id("ZONE", timeframe, "FVG", zone_type, float(gap["lower"]), float(gap["upper"])), "timeframe": timeframe, "zone_type": zone_type,
        "lower": float(gap["lower"]), "upper": float(gap["upper"]),
        "status": "INVALIDATED" if gap.get("status") == "MITIGATED" else "TOUCHED" if gap.get("touched") else "ACTIVE",
        "freshness": "USED" if gap.get("touched") else "FRESH", "available_at": gap.get("available_at"),
        "source_type": "FAIR_VALUE_GAP", "evidence_refs": evidence_union(gap) or [sanitize_id(gap["gap_id"])],
    }


def _zone_from_ob(candidate: dict[str, Any], timeframe: str) -> dict[str, Any]:
    zone_type = "DEMAND" if candidate["direction"] == "BULLISH" else "SUPPLY"
    return {
        "zone_id": semantic_id("ZONE", timeframe, "OB", zone_type, float(candidate["lower"]), float(candidate["upper"])), "timeframe": timeframe, "zone_type": zone_type,
        "lower": float(candidate["lower"]), "upper": float(candidate["upper"]), "status": "ACTIVE",
        "freshness": "FRESH", "available_at": candidate.get("available_at"),
        "source_type": "ORDER_BLOCK_CANDIDATE", "evidence_refs": evidence_union(candidate) or [sanitize_id(candidate["candidate_id"])],
    }


def _is_available_at_capture(zone: dict[str, Any], capture_time: str) -> bool:
    available_at = zone.get("available_at")
    return available_at is None or available_at <= capture_time


def _opposing_armed_opportunity_conflict(symbol: str, opportunities: list[dict[str, Any]]) -> dict[str, Any] | None:
    active = [
        item for item in opportunities
        if item["status"] in {"ARMED", "READY_FOR_ENTRY_EVALUATION"}
    ]
    if not {"BUY", "SELL"}.issubset({item["direction"] for item in active}):
        return None
    return {
        "conflict_id": semantic_id("CONFLICT", symbol, "OPPOSING_ARMED_OPPORTUNITIES"),
        "components": [f"{item['timeframe']}:{item['setup_family']}:{item['direction']}" for item in active],
        "message": "Opposing armed opportunities require one direction to resolve before review.",
        "blocking": True,
    }


def _dedupe_zones(zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, float, float], dict[str, Any]] = {}
    for zone in zones:
        key = (zone["zone_type"], round(zone["lower"], 8), round(zone["upper"], 8))
        if key not in unique:
            unique[key] = zone
    return list(unique.values())


def _working_zone_score(zone: dict[str, Any], reference_price: float) -> tuple[float, float, str]:
    width = max(float(zone["upper"]) - float(zone["lower"]), reference_price * 0.0005, 0.01)
    distance = _distance_to_zone(reference_price, zone) / width
    freshness = {"FRESH": 3.0, "USED": 1.5, "HEAVILY_USED": 0.0, "UNKNOWN": 0.0}.get(zone["freshness"], 0.0)
    status = {"ACTIVE": 2.0, "TOUCHED": 1.0, "DEGRADED": 0.0}.get(zone["status"], 0.0)
    source = {
        "SUPPORT_RESISTANCE": 2.0,
        "SUPPLY_DEMAND": 1.8,
        "ORDER_BLOCK_CANDIDATE": 1.5,
        "FAIR_VALUE_GAP": 1.0,
    }.get(zone.get("source_type"), 1.0)
    # Higher quality first; distance breaks ties without letting broad zones
    # dominate solely because they contain price.
    return (-(freshness + status + source - min(distance, 8.0) * 0.5), distance, zone["zone_id"])


def _select_working_zones(zones: list[dict[str, Any]], reference_price: float) -> list[dict[str, Any]]:
    """Bound decision zones while retaining raw sensor outputs as evidence."""
    eligible = [zone for zone in zones if zone["status"] not in {"INVALIDATED", "EXPIRED"}]
    selected: list[dict[str, Any]] = []
    for timeframe, limit in WORKING_ZONE_LIMITS.items():
        scoped = [zone for zone in eligible if zone.get("timeframe") == timeframe]
        selected.extend(sorted(scoped, key=lambda zone: _working_zone_score(zone, reference_price))[:limit])
    return sorted(selected, key=lambda zone: (zone.get("timeframe", ""), zone["zone_id"]))


def _liquidity(
    advanced_map: dict[tuple[str, str], dict[str, Any]],
    latest_price: float | None,
) -> dict[str, Any]:
    pools: list[dict[str, Any]] = []
    evidence: list[str] = []
    for (timeframe, sensor_name), result in advanced_map.items():
        if sensor_name != "liquidity_map":
            continue
        for pool in item_named(result, "liquidity_pools") or []:
            kind = "EQUAL_HIGH" if pool["type"] == "EQUAL_HIGHS" else "EQUAL_LOW"
            mapped = {
                "pool_id": sanitize_id(pool["pool_id"]),
                "timeframe": timeframe,
                "kind": kind,
                "lower": float(pool["lower"]),
                "upper": float(pool["upper"]),
                "status": "ACTIVE",
                "evidence_refs": evidence_union(pool) or [sanitize_id(pool["pool_id"])],
            }
            pools.append(mapped)
            evidence.extend(mapped["evidence_refs"])

    nearest_above = None
    nearest_below = None
    if latest_price is not None:
        above = [pool["lower"] for pool in pools if pool["lower"] > latest_price]
        below = [pool["upper"] for pool in pools if pool["upper"] < latest_price]
        nearest_above = min(above) if above else None
        nearest_below = max(below) if below else None

    return {
        "nearest_above": nearest_above,
        "nearest_below": nearest_below,
        "pools": pools,
        "evidence_refs": list(dict.fromkeys(evidence)),
    }


def _distance_to_zone(price: float, zone: dict[str, Any]) -> float:
    if zone["lower"] <= price <= zone["upper"]:
        return 0.0
    return min(abs(price - zone["lower"]), abs(price - zone["upper"]))


def _is_near_zone(price: float, zone: dict[str, Any]) -> bool:
    width = max(float(zone["upper"]) - float(zone["lower"]), 1e-6)
    # Setup location means at the zone, with only a small tolerance for spread
    # and quote granularity.  A multi-width distance is a watch condition, not
    # a valid zone-reaction setup.
    return _distance_to_zone(price, zone) <= max(width * 0.25, 0.01)


def _nearest_context_zone(
    zones: list[dict[str, Any]],
    *,
    price: float,
    side: str,
    event_timeframe: str,
) -> dict[str, Any] | None:
    allowed = {"DEMAND", "SUPPORT"} if side == "BUY" else {"SUPPLY", "RESISTANCE"}
    candidates = [
        zone for zone in zones
        if zone["zone_type"] in allowed
        and zone["status"] not in {"INVALIDATED", "EXPIRED"}
        and zone.get("timeframe") == event_timeframe
        and _is_near_zone(price, zone)
    ]
    if not candidates:
        return None
    freshness_rank = {"FRESH": 0, "USED": 1, "HEAVILY_USED": 2, "UNKNOWN": 3}
    return min(
        candidates,
        key=lambda zone: (_distance_to_zone(price, zone), freshness_rank.get(zone["freshness"], 4)),
    )


def build_market_packet(
    snapshot: dict[str, Any],
    basic: dict[str, Any],
    advanced: dict[str, Any],
    *,
    profile: str = "STANDARD",
) -> dict[str, Any]:
    basic_map = results_by_sensor(basic)
    advanced_map = results_by_sensor(advanced)
    all_timeframes = [item["timeframe"] for item in snapshot["timeframes"]]
    market_state = []
    structural_reference_price = None
    state_refs: list[str] = []

    events = all_events([basic, advanced])
    event_types_by_tf: dict[str, list[str]] = {}
    for event in events:
        event_types_by_tf.setdefault(event["timeframe"], []).append(event["event_type"])

    for timeframe_data in snapshot["timeframes"]:
        timeframe = timeframe_data["timeframe"]
        close = float(timeframe_data["bars"][-1]["close"])
        if timeframe == "M5" or structural_reference_price is None:
            structural_reference_price = close
        structure_result = basic_map.get((timeframe, "basic_structure"))
        trend_result = basic_map.get((timeframe, "trend_state"))
        range_result = basic_map.get((timeframe, "range_state"))
        volatility_result = basic_map.get((timeframe, "volatility_shock"))
        candle_result = basic_map.get((timeframe, "candle_features"))

        structure = _map_structure(
            _structure_value(structure_result),
            item_named(trend_result, "trend_state"),
            item_named(range_result, "range_state"),
        )
        volatility_value = item_named(volatility_result, "volatility_state")
        range_value = item_named(range_result, "range_state")
        trend_value = item_named(trend_result, "trend_state")
        recent_leg = _recent_leg(timeframe_data, structure, range_value)
        phase = _map_phase(
            structure,
            range_value,
            volatility_value,
            item_named(candle_result, "candle_direction"),
            event_types_by_tf.get(timeframe, []),
            recent_leg,
        )
        refs = evidence_union(
            structure_result,
            trend_result,
            range_result,
            volatility_result,
            candle_result,
        ) or snapshot["evidence_refs"]
        state_refs.extend(refs)
        market_state.append(
            {
                "timeframe": timeframe,
                "structure": structure,
                "regime": _map_regime(structure, range_value, trend_value),
                "recent_leg": recent_leg,
                "phase": phase,
                "volatility": _map_volatility(volatility_value),
                "evidence_refs": refs,
            }
        )

    zones: list[dict[str, Any]] = []
    location_labels: list[str] = []
    location_refs: list[str] = []
    for (timeframe, sensor_name), result in advanced_map.items():
        if sensor_name == "support_resistance":
            for zone in item_named(result, "support_resistance_zones") or []:
                mapped = _zone_from_sr(zone, timeframe)
                zones.append(mapped)
                location_refs.extend(mapped["evidence_refs"])
        elif sensor_name == "supply_demand_candidates":
            for zone in item_named(result, "supply_demand_candidates") or []:
                mapped = _zone_from_sd(zone, timeframe)
                if _is_available_at_capture(mapped, snapshot["capture_time"]):
                    zones.append(mapped)
                    location_refs.extend(mapped["evidence_refs"])
        elif sensor_name == "fair_value_gap":
            for gap in item_named(result, "fair_value_gaps") or []:
                mapped = _zone_from_fvg(gap, timeframe)
                if _is_available_at_capture(mapped, snapshot["capture_time"]):
                    zones.append(mapped)
                    location_refs.extend(mapped["evidence_refs"])
        elif sensor_name == "order_block_candidates":
            for candidate in item_named(result, "order_block_candidates") or []:
                mapped = _zone_from_ob(candidate, timeframe)
                if _is_available_at_capture(mapped, snapshot["capture_time"]):
                    zones.append(mapped)
                    location_refs.extend(mapped["evidence_refs"])
        elif sensor_name == "dealing_range":
            label = item_named(result, "dealing_range_location")
            if label:
                location_labels.append(f"{timeframe}_{label}")
                location_refs.extend(result["evidence_refs"])

    zones = _dedupe_zones(zones)
    observed_zone_count = len(zones)
    active_observed_zone_count = sum(zone["status"] not in {"INVALIDATED", "EXPIRED"} for zone in zones)
    live_quote = snapshot.get("quote", {})
    bid, ask = live_quote.get("bid"), live_quote.get("ask")
    live_mid = (
        (float(bid) + float(ask)) / 2.0
        if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and float(bid) > 0 and float(ask) >= float(bid)
        else None
    )
    working_reference_price = live_mid if live_mid is not None else structural_reference_price
    if working_reference_price is not None:
        zones = _select_working_zones(zones, working_reference_price)
    if structural_reference_price is not None:
        for zone in zones:
            if zone["lower"] <= structural_reference_price <= zone["upper"]:
                location_labels.append(f"IN_{zone['zone_type']}_{zone['zone_id']}")
            elif zone["upper"] < structural_reference_price:
                distance = structural_reference_price - zone["upper"]
                if distance <= max(zone["upper"] - zone["lower"], 1e-9) * 2:
                    location_labels.append(f"NEAR_{zone['zone_type']}_{zone['zone_id']}")
            else:
                distance = zone["lower"] - structural_reference_price
                if distance <= max(zone["upper"] - zone["lower"], 1e-9) * 2:
                    location_labels.append(f"NEAR_{zone['zone_type']}_{zone['zone_id']}")

    liquidity = _liquidity(advanced_map, structural_reference_price)
    confirmed_event_ids = [sanitize_id(event["event_id"]) for event in events]

    event_type_direction = [(event["event_type"], event["direction"]) for event in events]
    risk_flags: list[dict[str, Any]] = []
    for state in market_state:
        if state["volatility"] == "SHOCK":
            risk_flags.append(
                {
                    "code": f"SHOCK_{state['timeframe']}",
                    "severity": "BLOCK",
                    "message": f"{state['timeframe']} closed-bar shock detected.",
                    "evidence_refs": state["evidence_refs"],
                }
            )

    conflicts: list[dict[str, Any]] = []
    directional = [(state["timeframe"], state["structure"]) for state in market_state if state["structure"] in {"BULLISH", "BEARISH"}]
    if len({direction for _, direction in directional}) > 1:
        conflicts.append(
            {
                "conflict_id": sanitize_id(f"CONFLICT_MTF_STRUCTURE_{snapshot['snapshot_id']}"),
                "components": [f"{tf}:{direction}" for tf, direction in directional],
                "message": "Directional structure conflicts across timeframes.",
                "blocking": False,
            }
        )

    unknowns: list[dict[str, Any]] = []
    for envelope in [basic, advanced]:
        for result in envelope["results"]:
            for unknown in result.get("unknowns", []):
                unknowns.append(
                    {
                        "code": f"{result['timeframe']}_{unknown['code']}",
                        "message": unknown["message"],
                        "blocking": bool(unknown["blocking"]),
                    }
                )
    # Dedupe unknowns by code.
    unknowns = list({item["code"]: item for item in unknowns}.values())

    opportunities: list[dict[str, Any]] = []
    # A sweep/reclaim setup is valid only when the events and zone share a
    # timeframe and the execution price is actually at that zone.
    if structural_reference_price is not None:
        for side, direction in (("BUY", "BULLISH"), ("SELL", "BEARISH")):
            for timeframe in all_timeframes:
                scoped = [event for event in events if event["timeframe"] == timeframe and event["direction"] == direction]
                has_sweep = any(event["event_type"] == "SWEEP" for event in scoped)
                has_reclaim = any(event["event_type"] == "RECLAIM" for event in scoped)
                if not (has_sweep or has_reclaim):
                    continue
                zone = _nearest_context_zone(zones, price=structural_reference_price, side=side, event_timeframe=timeframe)
                if zone is None:
                    continue
                status = "READY_FOR_ENTRY_EVALUATION" if has_reclaim else "ARMED"
                opportunities.append(
                    {
                        "opportunity_id": semantic_id("OPP", snapshot["symbol"], "SR1", side, timeframe, zone["zone_id"]),
                        "setup_family": "SR1_SWEEP_RECLAIM_RETEST",
                        "status": status,
                        "direction": side,
                        "timeframe": timeframe,
                        "evidence_refs": evidence_union(zone, scoped) or snapshot["evidence_refs"],
                    }
                )
                break

    # Break scenarios use the execution timeframe only; a higher-timeframe
    # event cannot silently create an intraday execution candidate.
    execution_timeframe = "M5" if "M5" in all_timeframes else all_timeframes[0]
    for direction, side in (("BULLISH", "BUY"), ("BEARISH", "SELL")):
        scoped_breaks = [
            event for event in events
            if event["timeframe"] == execution_timeframe
            and event["event_type"] == "BREAK"
            and event["direction"] == direction
        ]
        if scoped_breaks:
            opportunities.append(
                {
                    "opportunity_id": semantic_id("OPP", snapshot["symbol"], "BR1", side, execution_timeframe, scoped_breaks[0].get("level")),
                    "setup_family": "BR1_BREAK_RETEST_CONTINUATION",
                    "status": "READY_FOR_ENTRY_EVALUATION",
                    "direction": side,
                    "timeframe": execution_timeframe,
                    "evidence_refs": evidence_union(scoped_breaks) or snapshot["evidence_refs"],
                }
            )

    missing_events = []
    if any(item["setup_family"].startswith("SR1") for item in opportunities):
        has_sweep = any(event["event_type"] == "SWEEP" for event in events)
        has_reclaim = any(event["event_type"] == "RECLAIM" for event in events)
        if not has_sweep:
            missing_events.append("LIQUIDITY_SWEEP")
        if not has_reclaim:
            missing_events.append("CLOSED_BAR_RECLAIM")
        missing_events.append("RETEST_HOLD")
    if any(item["setup_family"].startswith("BR1") for item in opportunities):
        missing_events.append("RETEST_FAIL_OR_HOLD_IN_BREAK_DIRECTION")
    missing_events = list(dict.fromkeys(missing_events))

    opportunity_conflict = _opposing_armed_opportunity_conflict(snapshot["symbol"], opportunities)
    if opportunity_conflict:
        conflicts.append(opportunity_conflict)

    evidence_refs = evidence_union(
        snapshot.get("evidence_refs", []),
        basic,
        advanced,
        zones,
        liquidity,
        opportunities,
    ) or [sanitize_id(f"EVID_{snapshot['snapshot_id']}")]

    return {
        "schema_version": "0.2.0",
        "market_packet_id": sanitize_id(f"MARKET_PACKET_{snapshot['snapshot_id']}"),
        "run_id": snapshot["run_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "symbol": snapshot["symbol"],
        "profile": profile,
        "generated_at": snapshot["capture_time"],
        "data_quality": {
            "source": snapshot.get("source"),
            "freshness": snapshot.get("freshness", {}).get("status"),
            "qc_decision": snapshot.get("qc", {}).get("decision"),
            "terminal_connected": snapshot.get("terminal", {}).get("connected"),
        },
        "market_state": market_state,
        "location": {
            "status": "KNOWN" if location_labels else "PARTIAL" if zones else "UNKNOWN",
            "labels": list(dict.fromkeys(location_labels)),
            # Structural state remains closed-bar-only.  Live quote is recorded
            # separately so entry location can be revalidated without turning a
            # forming tick into structure evidence.
            "reference_price": structural_reference_price,
            "structural_reference_price": structural_reference_price,
            "live_bid": bid,
            "live_ask": ask,
            "live_mid": live_mid,
            "evidence_refs": list(dict.fromkeys(location_refs)),
        },
        "active_zones": zones,
        "zone_summary": {
            "observed_total": observed_zone_count,
            "active_observed_total": active_observed_zone_count,
            "working_total": len(zones),
            "per_timeframe_limit": WORKING_ZONE_LIMITS,
        },
        "liquidity": liquidity,
        "confirmed_events": list(dict.fromkeys(confirmed_event_ids)),
        "missing_events": missing_events,
        "opportunities": opportunities,
        "risk_flags": risk_flags,
        "conflicts": conflicts,
        "unknowns": unknowns,
        "permission_state": "NOT_EVALUATED",
        "evidence_refs": evidence_refs,
        "component_versions": {
            "fusion": "0.1.0",
            "basic_eyes": basic["suite"]["version"],
            "advanced_eyes": advanced["suite"]["version"],
        },
        "compactness": {
            "profile": profile,
            "raw_bars_embedded": False,
            "estimated_tokens": None,
        },
    }
