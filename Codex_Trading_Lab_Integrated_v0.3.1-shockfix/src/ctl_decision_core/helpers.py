from __future__ import annotations

import math
from typing import Any


def derived_map(result: dict[str, Any]) -> dict[str, Any]:
    return {item["name"]: item["value"] for item in result.get("derived", [])}


def facts_map(result: dict[str, Any]) -> dict[str, Any]:
    return {item["name"]: item["value"] for item in result.get("facts", [])}


def results_by_sensor(envelope: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (result["timeframe"], result["sensor"]["name"]): result
        for result in envelope["results"]
    }


def evidence_union(*values: Any) -> list[str]:
    refs: list[str] = []

    def collect(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            if value and value[0].isalpha() and value.upper() == value:
                refs.append(value)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "evidence_refs":
                    collect(item)
                elif key in {"event_id", "claim_id", "zone_id", "pool_id"}:
                    collect(item)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                collect(item)

    for value in values:
        collect(value)
    return list(dict.fromkeys(refs))


def sanitize_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value.upper())
    cleaned = cleaned.strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"X_{cleaned}"
    return cleaned[:127]


def semantic_id(prefix: str, *parts: Any) -> str:
    """Stable entity ID derived from market meaning, never a snapshot ID."""
    normalized = []
    for part in parts:
        if isinstance(part, float):
            normalized.append(f"{part:.8f}".rstrip("0").rstrip("."))
        elif part is None:
            normalized.append("NONE")
        else:
            normalized.append(str(part))
    return sanitize_id("_".join([prefix, *normalized]))


def item_named(result: dict[str, Any] | None, name: str) -> Any:
    if not result:
        return None
    for item in result.get("derived", []):
        if item["name"] == name:
            return item["value"]
    for item in result.get("facts", []):
        if item["name"] == name:
            return item["value"]
    return None


def event_types(result: dict[str, Any] | None) -> list[str]:
    if not result:
        return []
    return [event["event_type"] for event in result.get("events", [])]


def all_events(envelopes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for envelope in envelopes:
        for result in envelope["results"]:
            for event in result.get("events", []):
                events.append(
                    {
                        **event,
                        "timeframe": result["timeframe"],
                        "sensor": result["sensor"]["name"],
                    }
                )
    return events


def midpoint(lower: float, upper: float) -> float:
    return (lower + upper) / 2.0


def rr_for(side: str, entry: float, stop: float, target: float) -> float:
    risk = entry - stop if side == "BUY" else stop - entry
    reward = target - entry if side == "BUY" else entry - target
    if risk <= 0:
        return -1.0
    return reward / risk


def choose_target(
    side: str,
    entry: float,
    stop: float,
    liquidity: dict[str, Any],
    minimum_rr: float = 1.5,
) -> tuple[float, str]:
    risk = entry - stop if side == "BUY" else stop - entry
    fallback = entry + risk * 2.0 if side == "BUY" else entry - risk * 2.0
    candidate = nearest_liquidity(liquidity, reference_price=entry, side=side)
    if candidate is None:
        return fallback, "2R fallback because no opposite liquidity was available"
    rr = rr_for(side, entry, stop, float(candidate))
    if rr >= minimum_rr:
        return float(candidate), "nearest opposite liquidity"
    return fallback, "2R fallback because nearest liquidity had insufficient RR"


def nearest_liquidity(
    liquidity: dict[str, Any],
    *,
    reference_price: float,
    side: str,
) -> float | None:
    """Return liquidity on the reward side of one proposed entry.

    Packet-level nearest liquidity is useful as market context, but it must not
    be reused for a distant limit entry.  Targets are therefore resolved from
    the entry price itself.
    """
    pools = liquidity.get("pools", [])
    if side == "BUY":
        candidates = [float(pool["lower"]) for pool in pools if float(pool["lower"]) > reference_price]
        return min(candidates) if candidates else None
    candidates = [float(pool["upper"]) for pool in pools if float(pool["upper"]) < reference_price]
    return max(candidates) if candidates else None


def status_priority(status: str) -> int:
    return {
        "READY_FOR_ENTRY_EVALUATION": 4,
        "ARMED": 3,
        "WATCH": 2,
        "DEGRADED": 1,
        "INVALIDATED": 0,
    }.get(status, 0)
