from __future__ import annotations

from typing import Any


def render_current_action_plan(
    market_packet: dict[str, Any],
    scenario_packet: dict[str, Any],
    entry_packet: dict[str, Any],
) -> str:
    primary = next((item for item in scenario_packet["scenarios"] if item["rank"] == "PRIMARY"), None)
    alternatives = [item for item in scenario_packet["scenarios"] if item["rank"] != "PRIMARY"]
    candidates = entry_packet["candidates"]

    lines = [
        "# CURRENT ACTION PLAN",
        "",
        f"- Symbol: **{market_packet['symbol']}**",
        f"- Snapshot: `{market_packet['snapshot_id']}`",
        f"- Generated: `{market_packet['generated_at']}`",
        f"- Permission: **{market_packet['permission_state']}**",
        "",
        "## Market State",
    ]
    for state in market_packet["market_state"]:
        lines.append(
            f"- {state['timeframe']}: {state['structure']} / {state['phase']} / {state['volatility']}"
        )

    directional = [
        state for state in market_packet["market_state"]
        if state["timeframe"] in {"M5", "M15", "H1"}
    ]
    bearish_aligned = len(directional) == 3 and all(state.get("recent_leg") == "BEARISH_ROTATION" for state in directional)
    live_mid = market_packet.get("location", {}).get("live_mid")
    h4_demands = [
        zone for zone in market_packet.get("active_zones", [])
        if zone.get("timeframe") == "H4" and "DEMAND" in zone.get("zone_type", "")
    ]
    active_h4_demand = next(
        (zone for zone in h4_demands if live_mid is not None and zone["lower"] <= live_mid <= zone["upper"]),
        min(h4_demands, key=lambda zone: min(abs(live_mid - zone["lower"]), abs(live_mid - zone["upper"]))) if h4_demands and live_mid is not None else None,
    )
    inside_h4_demand = bool(active_h4_demand and live_mid is not None and active_h4_demand["lower"] <= live_mid <= active_h4_demand["upper"])
    above_h4_demand = bool(active_h4_demand and live_mid is not None and live_mid > active_h4_demand["upper"])
    demand_location = "INSIDE_H4_DEMAND" if inside_h4_demand else "PRICE_TRADING_ABOVE_DEMAND_EDGE" if above_h4_demand else "BELOW_H4_DEMAND_EDGE" if active_h4_demand else market_packet.get("location", {}).get("status", "UNKNOWN")
    lines.extend(["", "## Alignment / Location / Permission"])
    lines.append(f"- Direction alignment: **{'M5-M15-H1 BEARISH' if bearish_aligned else 'MIXED_OR_UNCONFIRMED'}**")
    lines.append(f"- Location quality: **{demand_location}**")
    if active_h4_demand:
        lines.append(f"- H4 demand bounds: **{active_h4_demand['lower']:.5f}-{active_h4_demand['upper']:.5f}**")
        lines.append("- Trading above the demand edge is not RECLAIM_BULLISH_CONFIRMED.")
    lines.append("- Execution-quality alignment: **NOT_READY**")
    lines.append("- Execution permission: **NO**")

    m15 = next((state for state in market_packet["market_state"] if state["timeframe"] == "M15"), {})
    post_shock = m15.get("volatility") in {"HIGH", "SHOCK"} and m15.get("recent_leg") == "BEARISH_ROTATION"
    lines.extend(["", "## Primary Operational Scenario"])
    lines.append(f"- **{'POST_SHOCK_STABILIZATION' if post_shock else 'STRUCTURE_RESOLUTION'}**")
    lines.append("- Classification: **OBSERVATION_STATE; NOT_A_DIRECTIONAL_ENTRY_SIGNAL**")
    if post_shock:
        lines.extend(
            [
                "- M5 lower-low momentum: **PAUSED_NOT_CONFIRMED_STOPPED**",
                "- Bullish branch: current low holds -> M5 reclaim close -> retest hold -> higher low -> M15 base/follow-through",
                "- Bearish branch: M15 acceptance below H4 demand -> follow-through -> retest fail",
                "- Confirmation hierarchy: M15 close = WATCH; H1 close = STRONGER_CONFIRMATION; H4 close = HTF_STRUCTURAL_CONFIRMATION",
                "- A wick below H4 demand is not BREAK_BEARISH.",
            ]
        )
    elif active_h4_demand:
        lines.extend(
            [
                f"- M15 close below {active_h4_demand['upper']:.5f}: **REENTRY_INTO_H4_DEMAND / BULLISH_RECLAIM_WARNING**",
                f"- Acceptance below {active_h4_demand['lower']:.5f}: **H4_DEMAND_STRUCTURAL_FAILURE_WATCH**",
                "- Full bearish confirmation still requires follow-through and retest failure.",
                "- A wick below either boundary is not BREAK_BEARISH.",
            ]
        )

    lines.extend(["", "## Directional Branch Scenario"])
    if primary:
        lines.extend(
            [
                f"- {primary['label']}",
                f"- Status: **{'ARMED_FOR_OBSERVATION' if primary['status'] == 'ARMED' else primary['status']}**",
                "- Permission readiness: **NOT_READY**",
                "- Execution permission: **NO**",
                f"- Direction: **{primary['direction']}**",
                f"- Wait for: {', '.join(primary['what_to_wait_for']) or 'No remaining scenario event'}",
            ]
        )
    else:
        lines.append("- No primary scenario")

    lines.extend(["", "## Alternative Scenarios"])
    for scenario in alternatives[:3]:
        lines.append(f"- {scenario['rank']}: {scenario['label']} — {scenario['status']}")

    lines.extend(["", "## Entry Candidates"])
    if not candidates:
        lines.append("- No candidate generated from the current deterministic state.")
    for candidate in candidates[:6]:
        future_bearish_role_flip = bool(
            candidate.get("side") == "SELL"
            and "BREAK_BEARISH" in candidate.get("missing_conditions", [])
        )
        lines.extend(
            [
                f"### {candidate['candidate_id']}",
                f"- Type: {candidate['entry_type']} | Side: {candidate['side']} | Status: {candidate['status']}",
                f"- Entry: {candidate['entry_range']['lower']:.5f}–{candidate['entry_range']['upper']:.5f}",
                f"- Stop: {candidate['stop']['price']:.5f}",
                f"- TP1: {candidate['targets'][0]['price']:.5f}",
                f"- RR: {candidate['rr']['to_first_target']:.2f}",
                f"- Limit eligibility: {candidate['limit_eligibility']}",
                f"- Missing: {', '.join(candidate['missing_conditions']) or 'None'}",
                f"- Market role: {'FUTURE_BEARISH_ROLE_FLIP; NOT_A_CURRENT_ENTRY_ZONE' if future_bearish_role_flip else 'CURRENT_CONDITIONAL_CANDIDATE'}",
                "",
            ]
        )

    prohibited = []
    if primary:
        prohibited.extend(primary["prohibited_actions"])
    if any(flag["severity"] == "BLOCK" for flag in market_packet["risk_flags"]):
        prohibited.append("No new normal-logic entry while a blocking risk flag is active.")

    lines.extend(["## What Is Prohibited"])
    for item in list(dict.fromkeys(prohibited)) or ["Do not interpret this packet as trade permission."]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Contract",
            "- Runtime connection, quote, flags, scenario and candidate fields are FACT_FROM_RUNTIME_ARTIFACT.",
            "- Candle geometry and visible zone interaction are FACT_FROM_CHART.",
            "- Chart-derived interpretation must not be presented as runtime-verified fact.",
            "- Scenario rank is not probability.",
            "- LIMIT_READY is not permission.",
            "- All candidates require a separate Part 3 review.",
        ]
    )
    return "\n".join(lines) + "\n"
