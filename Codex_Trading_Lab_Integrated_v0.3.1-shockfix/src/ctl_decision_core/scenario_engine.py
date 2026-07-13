from __future__ import annotations

from typing import Any

from .helpers import evidence_union, sanitize_id, semantic_id, status_priority


def _confirmed_event_types(
    basic: dict[str, Any],
    advanced: dict[str, Any],
    *,
    timeframe: str | None = None,
) -> set[tuple[str, str]]:
    values = set()
    for envelope in [basic, advanced]:
        for result in envelope["results"]:
            if timeframe is not None and result["timeframe"] != timeframe:
                continue
            for event in result.get("events", []):
                values.add((event["event_type"], event["direction"]))
    return values


def _path_state(event_name: str, confirmed: set[tuple[str, str]]) -> str:
    mapping = {
        "SWEEP_LOW": ("SWEEP", "BULLISH"),
        "RECLAIM_BULLISH": ("RECLAIM", "BULLISH"),
        "SWEEP_HIGH": ("SWEEP", "BEARISH"),
        "RECLAIM_BEARISH": ("RECLAIM", "BEARISH"),
        "BREAK_BULLISH": ("BREAK", "BULLISH"),
        "BREAK_BEARISH": ("BREAK", "BEARISH"),
    }
    key = mapping.get(event_name)
    if key and key in confirmed:
        return "CONFIRMED"
    if event_name == "SHOCK" and any(event == "SHOCK" for event, _ in confirmed):
        return "CONFIRMED"
    return "PENDING"


def _scenario_status(path: list[dict[str, Any]], risk_block: bool) -> str:
    if risk_block:
        return "DEGRADED"
    confirmed = sum(1 for item in path if item["state"] == "CONFIRMED")
    if confirmed == len(path):
        return "READY_FOR_ENTRY_EVALUATION"
    if confirmed >= 2:
        return "CONFIRMING"
    if confirmed == 1:
        return "ARMED"
    return "WATCHING"


def build_scenario_packet(
    market_packet: dict[str, Any],
    basic: dict[str, Any],
    advanced: dict[str, Any],
) -> dict[str, Any]:
    blocking_risk = any(flag["severity"] == "BLOCK" for flag in market_packet["risk_flags"])
    opportunities = sorted(
        market_packet["opportunities"],
        key=lambda item: status_priority(item["status"]),
        reverse=True,
    )
    scenarios: list[dict[str, Any]] = []

    def add_scenario(
        *,
        suffix: str,
        rank: str,
        label: str,
        direction: str,
        path_events: list[str],
        invalidations: list[dict[str, str]],
        entry_types: list[str],
        evidence_refs: list[str],
        prohibited: list[str],
        confirmed_events: set[tuple[str, str]],
        degrade_on_risk: bool = True,
        identity: str | None = None,
    ) -> None:
        path = []
        for index, event_name in enumerate(path_events, start=1):
            state = _path_state(event_name, confirmed_events)
            path.append(
                {
                    "step": index,
                    "event": event_name,
                    "state": state,
                    "evidence_refs": evidence_refs if state == "CONFIRMED" else [],
                }
            )
        missing = [item["event"] for item in path if item["state"] == "PENDING"]
        scenarios.append(
            {
                "scenario_id": semantic_id("SCN", market_packet["symbol"], identity or suffix, direction),
                "rank": rank,
                "label": label,
                "direction": direction,
                "status": _scenario_status(path, blocking_risk and degrade_on_risk),
                "current_state": f"{direction}_{path[0]['event']}_{path[0]['state']}",
                "path": path,
                "required_events": path_events,
                "missing_events": missing,
                "invalidations": invalidations,
                "expiry": {
                    "mode": "BARS",
                    "expires_at": None,
                    "bars_remaining": 6,
                    "event": None,
                },
                "what_to_wait_for": missing[:3],
                "prohibited_actions": prohibited,
                "candidate_entry_types": entry_types,
                "evidence_refs": evidence_refs or market_packet["evidence_refs"],
            }
        )

    def add_opportunity_scenario(opportunity: dict[str, Any], rank: str, index: int) -> None:
        side = opportunity["direction"]
        bullish = side == "BUY"
        direction = "BULLISH" if bullish else "BEARISH"
        setup = opportunity["setup_family"]
        refs = opportunity["evidence_refs"]
        confirmed_events = _confirmed_event_types(
            basic,
            advanced,
            timeframe=opportunity.get("timeframe"),
        )

        if setup == "BR1_BREAK_RETEST_CONTINUATION":
            break_event = "BREAK_BULLISH" if bullish else "BREAK_BEARISH"
            add_scenario(
                suffix=f"BR1_{side}_{index}",
                rank=rank,
                label=f"{direction.title()} break, retest and continuation",
                direction=direction,
                path_events=[break_event, "RETEST_HOLD", "CONTINUATION"],
                invalidations=[
                    {
                        "rule_id": f"INV_BR1_{side}",
                        "condition": "Closed bar reclaims the broken level against the continuation direction",
                        "action": "INVALIDATE",
                    },
                    {
                        "rule_id": "DEG_SHOCK",
                        "condition": "Shock becomes active",
                        "action": "DEGRADE",
                    },
                ],
                entry_types=["EARLY_CONFIRMATION", "FULL_CONFIRMATION", "CONTINUATION"],
                evidence_refs=refs,
                prohibited=[
                    "Do not call a wick-through a confirmed break",
                    "Do not chase after the continuation window has expired",
                    "Do not treat scenario rank as permission",
                ],
                confirmed_events=confirmed_events,
                identity=opportunity["opportunity_id"],
            )
        else:
            sweep_event = "SWEEP_LOW" if bullish else "SWEEP_HIGH"
            reclaim_event = "RECLAIM_BULLISH" if bullish else "RECLAIM_BEARISH"
            add_scenario(
                suffix=f"SR1_{side}_{index}",
                rank=rank,
                label=f"{direction.title()} zone reaction through sweep, reclaim and retest",
                direction=direction,
                path_events=[sweep_event, reclaim_event, "RETEST_HOLD"],
                invalidations=[
                    {
                        "rule_id": f"INV_SR1_{side}",
                        "condition": "Closed bar invalidates the supporting zone",
                        "action": "INVALIDATE",
                    },
                    {
                        "rule_id": "DEG_SHOCK",
                        "condition": "Shock becomes active",
                        "action": "DEGRADE",
                    },
                ],
                entry_types=["STRUCTURED_LIMIT", "EARLY_CONFIRMATION", "FULL_CONFIRMATION"],
                evidence_refs=refs,
                prohibited=[
                    "Do not chase outside the defined entry window",
                    "Do not treat scenario rank as permission",
                ],
                confirmed_events=confirmed_events,
                identity=opportunity["opportunity_id"],
            )

    # Create scenarios from up to two strongest opportunities.
    for index, opportunity in enumerate(opportunities[:2], start=1):
        add_opportunity_scenario(
            opportunity,
            "PRIMARY" if index == 1 else "SECONDARY",
            index,
        )

    if not opportunities:
        add_scenario(
            suffix="BALANCED",
            rank="PRIMARY",
            label="Market remains balanced until structure resolves",
            direction="RANGE",
            path_events=["RANGE_HOLD", "CLOSED_BAR_RESOLUTION"],
            invalidations=[
                {
                    "rule_id": "INV_RANGE_BREAK",
                    "condition": "Confirmed close outside the active range",
                    "action": "INVALIDATE",
                }
            ],
            entry_types=["STRUCTURED_LIMIT", "FULL_CONFIRMATION"],
            evidence_refs=market_packet["evidence_refs"],
            prohibited=[
                "Do not trade the center of the range",
                "Do not invent directional confirmation",
            ],
            confirmed_events=_confirmed_event_types(basic, advanced),
        )

    # Add opposite-direction failure of the current primary opportunity.
    if opportunities:
        primary_side = opportunities[0]["direction"]
        failure_bullish = primary_side == "SELL"
        failure_direction = "BULLISH" if failure_bullish else "BEARISH"
        failure_break = "BREAK_BULLISH" if failure_bullish else "BREAK_BEARISH"
        add_scenario(
            suffix=f"FAILURE_{failure_direction}",
            rank="LOWER_PRIORITY",
            label=f"Primary setup fails and {failure_direction.lower()} continuation develops",
            direction=failure_direction,
            path_events=[failure_break, "RETEST_HOLD", "CONTINUATION"],
            invalidations=[
                {
                    "rule_id": "INV_FAILURE_RECLAIM",
                    "condition": "Price reclaims the failed level against the failure direction",
                    "action": "INVALIDATE",
                }
            ],
            entry_types=["EARLY_CONFIRMATION", "FULL_CONFIRMATION", "CONTINUATION"],
            evidence_refs=market_packet["evidence_refs"],
            prohibited=[
                "Do not reverse before a closed-bar break",
                "Do not widen invalidation",
            ],
            confirmed_events=_confirmed_event_types(
                basic,
                advanced,
                timeframe=opportunities[0].get("timeframe"),
            ),
            identity=semantic_id("FAILURE", opportunities[0]["opportunity_id"], failure_direction),
        )

    add_scenario(
        suffix="ALTERNATIVE_BALANCE",
        rank="LOWER_PRIORITY",
        label="Compression or balance continues before the next directional move",
        direction="RANGE",
        path_events=["COMPRESSION_CONTINUES", "CLOSED_BAR_RESOLUTION"],
        invalidations=[
            {
                "rule_id": "EXP_BALANCE",
                "condition": "Directional resolution is confirmed",
                "action": "EXPIRE",
            }
        ],
        entry_types=["STRUCTURED_LIMIT", "FULL_CONFIRMATION"],
        evidence_refs=market_packet["evidence_refs"],
        prohibited=[
            "Avoid entries in the middle of balance",
            "Wait for edge or resolution",
        ],
        confirmed_events=_confirmed_event_types(basic, advanced),
    )

    add_scenario(
        suffix="TAIL_SHOCK",
        rank="TAIL_RISK",
        label="Shock invalidates normal scenario assumptions",
        direction="NEUTRAL",
        path_events=["SHOCK", "POST_SHOCK_STABILIZATION"],
        invalidations=[
            {
                "rule_id": "EXP_SHOCK",
                "condition": "Volatility normalizes and structure is re-established",
                "action": "EXPIRE",
            }
        ],
        entry_types=[],
        evidence_refs=market_packet["evidence_refs"],
        prohibited=["No new normal-logic entry during active shock"],
        confirmed_events=_confirmed_event_types(basic, advanced),
        degrade_on_risk=False,
    )

    if blocking_risk:
        for scenario in scenarios:
            if scenario["rank"] == "PRIMARY":
                scenario["rank"] = "SECONDARY"
            elif scenario["rank"] == "TAIL_RISK":
                scenario["rank"] = "PRIMARY"
                scenario["status"] = (
                    "ARMED"
                    if any(item["state"] == "CONFIRMED" for item in scenario["path"])
                    else "WATCHING"
                )

    evidence_refs = evidence_union(market_packet, scenarios) or market_packet["evidence_refs"]
    return {
        "schema_version": "0.2.0",
        "scenario_packet_id": sanitize_id(f"SCENARIO_PACKET_{market_packet['snapshot_id']}"),
        "run_id": market_packet["run_id"],
        "snapshot_id": market_packet["snapshot_id"],
        "market_packet_id": market_packet["market_packet_id"],
        "symbol": market_packet["symbol"],
        "generated_at": market_packet["generated_at"],
        "ranking_method": "QUALITATIVE_RULE_BASED",
        "probability_status": "UNAVAILABLE_UNTIL_CALIBRATED",
        "scenarios": scenarios[:8],
        "evidence_refs": evidence_refs,
    }
