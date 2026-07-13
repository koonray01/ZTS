from __future__ import annotations

from typing import Any

from .helpers import choose_target, evidence_union, midpoint, rr_for, sanitize_id, semantic_id
from .limit_gate import evaluate_limit_eligibility


def _scenario_side(direction: str) -> str | None:
    if direction == "BULLISH":
        return "BUY"
    if direction == "BEARISH":
        return "SELL"
    return None


def _zones_for_side(market_packet: dict[str, Any], side: str) -> list[dict[str, Any]]:
    allowed = {"DEMAND", "SUPPORT"} if side == "BUY" else {"SUPPLY", "RESISTANCE"}
    return [
        zone for zone in market_packet["active_zones"]
        if zone["zone_type"] in allowed and zone["status"] not in {"INVALIDATED", "EXPIRED"}
    ]


def _distance_to_zone(price: float, zone: dict[str, Any]) -> float:
    if zone["lower"] <= price <= zone["upper"]:
        return 0.0
    return min(abs(price - zone["lower"]), abs(price - zone["upper"]))


def _is_at_location(price: float, zone: dict[str, Any]) -> bool:
    width = max(float(zone["upper"]) - float(zone["lower"]), 1e-6)
    return _distance_to_zone(price, zone) <= max(width * 0.25, 0.01)


def _select_zone(
    market_packet: dict[str, Any],
    side: str,
    *,
    reference_price: float | None,
) -> dict[str, Any] | None:
    zones = _zones_for_side(market_packet, side)
    if not zones:
        return None
    freshness_rank = {"FRESH": 3, "USED": 2, "UNKNOWN": 1, "HEAVILY_USED": 0}
    status_rank = {"ACTIVE": 2, "TOUCHED": 1, "DEGRADED": 0}
    if reference_price is not None:
        zones = [zone for zone in zones if _is_at_location(reference_price, zone)]
    if not zones:
        return None
    zones.sort(
        key=lambda zone: (
            _distance_to_zone(reference_price, zone) if reference_price is not None else 0.0,
            -freshness_rank.get(zone["freshness"], 0),
            -status_rank.get(zone["status"], 0),
        ),
        reverse=False,
    )
    return zones[0]


def _stop_for_zone(side: str, zone: dict[str, Any]) -> float:
    width = max(zone["upper"] - zone["lower"], 1e-6)
    buffer = max(width * 0.20, 1e-6)
    return zone["lower"] - buffer if side == "BUY" else zone["upper"] + buffer


def _quality_enhancers(market_packet: dict[str, Any], side: str) -> list[dict[str, str]]:
    states = {item["timeframe"]: item["structure"] for item in market_packet["market_state"]}
    aligned = sum(
        1 for structure in states.values()
        if (side == "BUY" and structure == "BULLISH") or (side == "SELL" and structure == "BEARISH")
    )
    conflicting = sum(
        1 for structure in states.values()
        if (side == "BUY" and structure == "BEARISH") or (side == "SELL" and structure == "BULLISH")
    )
    return [
        {
            "name": "MULTI_TIMEFRAME_ALIGNMENT",
            "status": "PRESENT" if aligned > conflicting and aligned > 0 else "CONFLICTING" if conflicting else "UNKNOWN",
            "impact": "UNVALIDATED",
        },
        {
            "name": "OPPOSITE_LIQUIDITY_TARGET",
            "status": "PRESENT" if (
                market_packet["liquidity"]["nearest_above"] is not None if side == "BUY"
                else market_packet["liquidity"]["nearest_below"] is not None
            ) else "ABSENT",
            "impact": "UNVALIDATED",
        },
        {
            "name": "DEALING_RANGE_LOCATION",
            "status": "PRESENT" if market_packet["location"]["labels"] else "UNKNOWN",
            "impact": "UNVALIDATED",
        },
    ]


def build_entry_packet(
    market_packet: dict[str, Any],
    scenario_packet: dict[str, Any],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    location = market_packet.get("location", {})
    reference_price = location.get("structural_reference_price", location.get("reference_price"))
    live_location_price = location.get("live_mid", reference_price)

    for scenario in scenario_packet["scenarios"]:
        side = _scenario_side(scenario["direction"])
        if side is None or scenario["rank"] == "TAIL_RISK":
            continue

        zone = _select_zone(market_packet, side, reference_price=reference_price)
        if zone is None and "CONTINUATION" not in scenario["candidate_entry_types"]:
            continue

        entry_types = scenario["candidate_entry_types"]
        # Keep candidate count bounded and useful.
        for entry_type in entry_types[:3]:
            if entry_type == "STRUCTURED_LIMIT" and zone is None:
                continue

            if zone is not None:
                lower, upper = float(zone["lower"]), float(zone["upper"])
                base_entry = midpoint(lower, upper)
                stop = _stop_for_zone(side, zone)
            else:
                # Continuation fallback uses liquidity as a reference band.
                current_target = (
                    market_packet["liquidity"]["nearest_above"]
                    if side == "BUY"
                    else market_packet["liquidity"]["nearest_below"]
                )
                if current_target is None:
                    continue
                base_entry = float(current_target)
                width = max(abs(base_entry) * 0.0005, 0.01)
                lower, upper = base_entry - width, base_entry + width
                stop = lower - width if side == "BUY" else upper + width

            target, target_basis = choose_target(
                side,
                base_entry,
                stop,
                market_packet["liquidity"],
            )
            rr = rr_for(side, base_entry, stop, target)
            limit_status, limit_checks = evaluate_limit_eligibility(
                zone=zone,
                rr=rr,
                risk_flags=market_packet["risk_flags"],
                conflicts=market_packet["conflicts"],
                invalidation_clear=True,
                at_location=bool(zone and live_location_price is not None and _is_at_location(live_location_price, zone)),
            )

            missing = list(scenario["missing_events"])
            at_live_location = bool(zone and live_location_price is not None and _is_at_location(live_location_price, zone))
            if zone and not at_live_location:
                missing.append("PRICE_LEFT_LOCATION")
            if entry_type == "STRUCTURED_LIMIT":
                trigger_mode = "NONE_FOR_LIMIT"
                trigger_status = "NOT_REQUIRED"
                required_events = []
                candidate_status = "WAIT" if limit_status in {"LIMIT_READY", "LIMIT_WATCH", "CONFIRMATION_REQUIRED"} else "REJECTED"
            elif entry_type == "EARLY_CONFIRMATION":
                trigger_mode = "EVENT_SEQUENCE"
                required_events = scenario["required_events"][:2]
                relevant_missing = [event for event in required_events if event in missing]
                trigger_status = "SATISFIED" if not relevant_missing else "PENDING"
                candidate_status = "WAIT"
                limit_status = "NOT_APPLICABLE"
            elif entry_type == "FULL_CONFIRMATION":
                trigger_mode = "EVENT_SEQUENCE"
                required_events = scenario["required_events"]
                relevant_missing = [event for event in required_events if event in missing]
                trigger_status = "SATISFIED" if not relevant_missing else "PENDING"
                candidate_status = "WAIT"
                limit_status = "NOT_APPLICABLE"
            else:
                trigger_mode = "CLOSED_BAR"
                required_events = ["BREAK_IN_DIRECTION", "RETEST_OR_HOLD"]
                trigger_status = "PENDING"
                candidate_status = "WAIT"
                limit_status = "NOT_APPLICABLE"

            hard_requirements = [
                {
                    "requirement_id": "LOCATION",
                    "status": "PASS" if zone and at_live_location else "PENDING",
                    "message": (
                        "Live quote remains at the traceable zone."
                        if zone and at_live_location
                        else "Live quote has left the selected zone."
                        if zone
                        else "Continuation location pending."
                    ),
                },
                {
                    "requirement_id": "STRUCTURAL_INVALIDATION",
                    "status": "PASS",
                    "message": "Stop is placed beyond the structural candidate boundary.",
                },
                {
                    "requirement_id": "MINIMUM_RR",
                    "status": "PASS" if rr >= 1.5 else "FAIL",
                    "message": f"Calculated RR={rr:.2f}.",
                },
                {
                    "requirement_id": "NO_BLOCKING_RISK",
                    "status": "FAIL" if any(flag["severity"] == "BLOCK" for flag in market_packet["risk_flags"]) else "PASS",
                    "message": "Blocking risk checked.",
                },
                {
                    "requirement_id": "NO_UNRESOLVED_MTF_CONFLICT",
                    "status": "PENDING" if market_packet["conflicts"] else "PASS",
                    "message": "Multi-timeframe conflict requires resolution." if market_packet["conflicts"] else "No multi-timeframe conflict remains.",
                },
            ]
            if entry_type == "STRUCTURED_LIMIT":
                hard_requirements.extend(limit_checks)

            all_requirements_pass = all(item["status"] == "PASS" for item in hard_requirements)
            ready = (
                not missing
                and all_requirements_pass
                and (
                    limit_status == "LIMIT_READY"
                    if entry_type == "STRUCTURED_LIMIT"
                    else trigger_status == "SATISFIED"
                )
            )
            if ready:
                candidate_status = "READY_FOR_PERMISSION_REVIEW"

            evidence_refs = evidence_union(
                scenario,
                zone,
                market_packet["liquidity"],
            ) or market_packet["evidence_refs"]

            candidates.append(
                {
                    "candidate_id": semantic_id(
                        "ENTRY", scenario["scenario_id"], entry_type, side,
                        zone["zone_id"] if zone else "CONTINUATION",
                    ),
                    "scenario_id": scenario["scenario_id"],
                    "entry_type": entry_type,
                    "side": side,
                    "status": candidate_status,
                    "grade": "UNSCORED",
                    "entry_range": {"lower": min(lower, upper), "upper": max(lower, upper)},
                    "trigger": {
                        "mode": trigger_mode,
                        "required_events": required_events,
                        "status": trigger_status,
                    },
                    "hard_requirements": hard_requirements,
                    "quality_enhancers": _quality_enhancers(market_packet, side),
                    "missing_conditions": missing,
                    "invalidation": {
                        "description": "Closed-bar structural invalidation beyond the selected zone/reference.",
                        "level": stop,
                        "evidence_refs": evidence_refs,
                    },
                    "stop": {
                        "price": stop,
                        "basis": "ZONE" if zone else "STRUCTURE",
                    },
                    "targets": [
                        {
                            "label": "TP1",
                            "price": target,
                            "basis": target_basis,
                        }
                    ],
                    "rr": {
                        "minimum": 1.5,
                        "to_first_target": rr,
                        "calculation_basis": "mid-entry to structural stop and first target",
                    },
                    "entry_latency": {
                        "bars_since_first_opportunity": 0,
                        "status": "EARLY" if entry_type in {"STRUCTURED_LIMIT", "EARLY_CONFIRMATION"} else "TIMELY",
                    },
                    "expiry": {
                        "mode": "BARS",
                        "expires_at": None,
                        "bars_remaining": 4,
                        "event": None,
                    },
                    "limit_eligibility": limit_status,
                    "risk_mode": "UNASSESSED",
                    "permission_state": "NOT_EVALUATED",
                    "evidence_refs": evidence_refs,
                }
            )

    evidence_refs = evidence_union(market_packet, scenario_packet, candidates) or market_packet["evidence_refs"]
    return {
        "schema_version": "0.2.0",
        "entry_packet_id": sanitize_id(f"ENTRY_PACKET_{market_packet['snapshot_id']}"),
        "run_id": market_packet["run_id"],
        "snapshot_id": market_packet["snapshot_id"],
        "scenario_packet_id": scenario_packet["scenario_packet_id"],
        "symbol": market_packet["symbol"],
        "generated_at": market_packet["generated_at"],
        "candidates": candidates,
        "permission_state": "NOT_EVALUATED",
        "evidence_refs": evidence_refs,
    }
