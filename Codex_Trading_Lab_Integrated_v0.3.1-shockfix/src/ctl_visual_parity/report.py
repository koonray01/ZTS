from __future__ import annotations

from typing import Any


def _structure_status(engine: str, visual: str | None) -> str:
    if visual is None or visual == "UNKNOWN":
        return "UNKNOWN"
    if engine == visual:
        return "MATCH"
    if "TRANSITION" in {engine, visual}:
        return "PARTIAL_MATCH"
    return "MISMATCH"


def _leg_status(engine: str, visual: str | None) -> str:
    if visual is None or visual == "UNKNOWN" or engine == "UNKNOWN":
        return "UNKNOWN"
    if engine == visual:
        return "MATCH"
    # A direction match with different label (for example impulse vs rotation)
    # is informative but not a strict parity match.
    if engine.split("_", 1)[0] == visual.split("_", 1)[0]:
        return "PARTIAL_MATCH"
    return "MISMATCH"


def _zone_status(engine_zones: list[dict[str, Any]], visual_zones: list[dict[str, Any]]) -> str:
    if not visual_zones:
        return "UNKNOWN"
    for visual in visual_zones:
        for engine in engine_zones:
            if visual["zone_type"] != engine["zone_type"]:
                continue
            if float(visual["lower"]) <= float(engine["upper"]) and float(engine["lower"]) <= float(visual["upper"]):
                return "MATCH"
    return "MISMATCH"


def compare_visual_observation(market_packet: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    """Compare manually extracted screenshot facts with deterministic output.

    This is intentionally QA-only: screenshots never create events, zones, or
    permission.  They explain whether the closed-bar interpretation matches a
    chart captured at a known time.
    """
    states = {item["timeframe"]: item for item in market_packet["market_state"]}
    quote = market_packet.get("location", {}).get("live_mid")
    comparisons = []
    for item in observation["timeframes"]:
        timeframe = item["timeframe"]
        engine = states.get(timeframe)
        if engine is None:
            comparisons.append({"timeframe": timeframe, "status": "UNKNOWN", "reason": "TIMEFRAME_NOT_IN_MARKET_PACKET"})
            continue
        visual_structure = item.get("structure", {}).get("external") or item.get("structure", {}).get("internal")
        structure = _structure_status(engine["structure"], visual_structure)
        leg = _leg_status(engine["recent_leg"], item.get("recent_leg"))
        zones = _zone_status(
            [zone for zone in market_packet["active_zones"] if zone.get("timeframe") == timeframe],
            item.get("zones", []),
        )
        price_status = "UNKNOWN"
        if item.get("visible_price") is not None and quote is not None:
            price_status = "MATCH" if abs(float(item["visible_price"]) - float(quote)) <= float(observation["price_tolerance"]) else "MISMATCH"
        statuses = {structure, leg, zones, price_status}
        overall = "MISMATCH" if "MISMATCH" in statuses else "PARTIAL_MATCH" if {"PARTIAL_MATCH", "UNKNOWN"} & statuses else "MATCH"
        comparisons.append(
            {
                "timeframe": timeframe,
                "status": overall,
                "structure": {"status": structure, "engine": engine["structure"], "visual": visual_structure},
                "recent_leg": {"status": leg, "engine": engine["recent_leg"], "visual": item.get("recent_leg")},
                "zones": {"status": zones},
                "price": {"status": price_status, "engine_live_mid": quote, "visual": item.get("visible_price")},
            }
        )
    statuses = {item["status"] for item in comparisons}
    overall = "MISMATCH" if "MISMATCH" in statuses else "PARTIAL_MATCH" if statuses - {"MATCH"} else "MATCH"
    return {
        "schema_version": "0.1.0",
        "mode": "QA_ONLY_NO_PERMISSION_EFFECT",
        "symbol": market_packet["symbol"],
        "market_packet_id": market_packet["market_packet_id"],
        "observation_id": observation["observation_id"],
        "overall_status": overall,
        "timeframes": comparisons,
        "unknowns": ["Screenshot interpretation remains manual until an indicator-specific extractor is validated."],
    }
