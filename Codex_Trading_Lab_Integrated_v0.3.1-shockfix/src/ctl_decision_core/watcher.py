from __future__ import annotations

from typing import Any

from .helpers import sanitize_id


SIGNIFICANT_TYPES = {
    "MARKET_STATE_CHANGED",
    "SHOCK_DETECTED",
    "SHOCK_CLEARED",
    "ZONE_TOUCHED",
    "ZONE_INVALIDATED",
    "OPPORTUNITY_STATUS_CHANGED",
    "SCENARIO_RANK_CHANGED",
    "SCENARIO_STATUS_CHANGED",
    "ENTRY_WINDOW_OPENED",
    "ENTRY_INVALIDATED",
    "ENTRY_EXPIRED",
}


def _map_by(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {item[key]: item for item in items}


def diff_decision_state(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    *,
    seen_event_keys: set[str] | None = None,
) -> dict[str, Any]:
    seen = set(seen_event_keys or set())
    events: list[dict[str, Any]] = []

    def emit(event_type: str, entity_id: str, before: Any, after: Any, significant: bool = True) -> None:
        # Keep the complete transition: WAIT->READY and ARMED->READY are not
        # interchangeable, while the same transition is safely debounced.
        key = sanitize_id(f"{event_type}_{entity_id}_{before}_{after}")
        if key in seen:
            return
        seen.add(key)
        events.append(
            {
                "event_key": key,
                "event_type": event_type,
                "entity_id": entity_id,
                "before": before,
                "after": after,
                "significant": significant and event_type in SIGNIFICANT_TYPES,
            }
        )

    if previous is None:
        emit("INITIAL_STATE", current["market_packet"]["market_packet_id"], None, "CREATED", significant=False)
    else:
        prev_market = previous["market_packet"]
        curr_market = current["market_packet"]

        prev_states = _map_by(prev_market["market_state"], "timeframe")
        curr_states = _map_by(curr_market["market_state"], "timeframe")
        for timeframe, state in curr_states.items():
            before = prev_states.get(timeframe)
            if before and (
                before["structure"],
                before.get("regime"),
                before.get("recent_leg"),
                before["phase"],
                before["volatility"],
            ) != (
                state["structure"],
                state.get("regime"),
                state.get("recent_leg"),
                state["phase"],
                state["volatility"],
            ):
                emit(
                    "MARKET_STATE_CHANGED",
                    timeframe,
                    {
                        "structure": before["structure"],
                        "regime": before.get("regime"),
                        "recent_leg": before.get("recent_leg"),
                        "phase": before["phase"],
                        "volatility": before["volatility"],
                    },
                    {
                        "structure": state["structure"],
                        "regime": state.get("regime"),
                        "recent_leg": state.get("recent_leg"),
                        "phase": state["phase"],
                        "volatility": state["volatility"],
                    },
                )
            if before and before["volatility"] != "SHOCK" and state["volatility"] == "SHOCK":
                emit("SHOCK_DETECTED", timeframe, before["volatility"], "SHOCK")
            if before and before["volatility"] == "SHOCK" and state["volatility"] != "SHOCK":
                emit("SHOCK_CLEARED", timeframe, "SHOCK", state["volatility"])

        prev_zones = _map_by(prev_market["active_zones"], "zone_id")
        curr_zones = _map_by(curr_market["active_zones"], "zone_id")
        for zone_id, zone in curr_zones.items():
            before = prev_zones.get(zone_id)
            if before and before["status"] != zone["status"]:
                if zone["status"] == "TOUCHED":
                    emit("ZONE_TOUCHED", zone_id, before["status"], zone["status"])
                elif zone["status"] == "INVALIDATED":
                    emit("ZONE_INVALIDATED", zone_id, before["status"], zone["status"])

        prev_opps = _map_by(prev_market["opportunities"], "opportunity_id")
        for opp in curr_market["opportunities"]:
            before = prev_opps.get(opp["opportunity_id"])
            if before and before["status"] != opp["status"]:
                emit("OPPORTUNITY_STATUS_CHANGED", opp["opportunity_id"], before["status"], opp["status"])

        prev_scenarios = _map_by(previous["scenario_packet"]["scenarios"], "scenario_id")
        for scenario in current["scenario_packet"]["scenarios"]:
            before = prev_scenarios.get(scenario["scenario_id"])
            if before and before["rank"] != scenario["rank"]:
                emit("SCENARIO_RANK_CHANGED", scenario["scenario_id"], before["rank"], scenario["rank"])
            if before and before["status"] != scenario["status"]:
                emit("SCENARIO_STATUS_CHANGED", scenario["scenario_id"], before["status"], scenario["status"])

        prev_entries = _map_by(previous["entry_packet"]["candidates"], "candidate_id")
        for candidate in current["entry_packet"]["candidates"]:
            before = prev_entries.get(candidate["candidate_id"])
            if before and before["status"] != candidate["status"]:
                if candidate["status"] == "READY_FOR_PERMISSION_REVIEW":
                    emit("ENTRY_WINDOW_OPENED", candidate["candidate_id"], before["status"], candidate["status"])
                elif candidate["status"] == "INVALIDATED":
                    emit("ENTRY_INVALIDATED", candidate["candidate_id"], before["status"], candidate["status"])
                elif candidate["status"] == "EXPIRED":
                    emit("ENTRY_EXPIRED", candidate["candidate_id"], before["status"], candidate["status"])

    significant = [event for event in events if event["significant"]]
    return {
        "watcher_version": "0.1.0",
        "snapshot_id": current["market_packet"]["snapshot_id"],
        "events": events,
        "significant_events": significant,
        "should_trigger_codex": bool(significant),
        "seen_event_keys": sorted(seen),
    }
