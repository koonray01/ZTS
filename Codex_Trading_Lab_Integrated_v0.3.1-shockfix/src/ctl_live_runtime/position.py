from __future__ import annotations

from typing import Any

from .utils import sanitize_id


def _progress_r(position: dict[str, Any], current_price: float) -> float | None:
    entry = float(position["entry_price"])
    stop = position.get("initial_stop")
    if stop is None:
        return None
    stop = float(stop)
    side = position["side"]
    risk = entry - stop if side == "BUY" else stop - entry
    if risk <= 0:
        return None
    reward = current_price - entry if side == "BUY" else entry - current_price
    return reward / risk


def review_position(
    *,
    position: dict[str, Any],
    snapshot_id: str,
    current_price: float,
    market_packet: dict[str, Any],
    linked_scenario: dict[str, Any] | None,
    entry_record: dict[str, Any] | None,
) -> dict[str, Any]:
    progress = _progress_r(position, current_price)
    blocking_risk = any(flag["severity"] == "BLOCK" for flag in market_packet["risk_flags"])
    scenario_status = None if linked_scenario is None else linked_scenario["status"]

    if position.get("closed"):
        state = "CLOSED"
        integrity = "UNKNOWN"
        recommendation = "NONE"
        reasons = ["Position is observed as closed."]
    elif entry_record is None:
        state = "UNRECONCILED"
        integrity = "UNKNOWN"
        recommendation = "MANUAL_RECONCILIATION_REQUIRED"
        reasons = ["No entry record links this position to a plan or manual override."]
    elif scenario_status in {"INVALIDATED"}:
        state = "EXIT_REVIEW"
        integrity = "INVALIDATED"
        recommendation = "EXIT_REVIEW"
        reasons = ["Linked scenario is invalidated."]
    elif blocking_risk:
        state = "DEGRADED"
        integrity = "DEGRADED"
        recommendation = "REDUCE_REVIEW" if progress is not None and progress > 0 else "EXIT_REVIEW"
        reasons = ["Blocking market-risk flag is active."]
    elif progress is not None and progress >= 1.0 and not position.get("protected", False):
        state = "ACTIVE"
        integrity = "INTACT"
        recommendation = "PROTECT"
        reasons = [f"Position has progressed to {progress:.2f}R without recorded protection."]
    elif position.get("protected", False):
        state = "PROTECTED"
        integrity = "INTACT"
        recommendation = "HOLD"
        reasons = ["Position is protected and scenario remains intact."]
    else:
        state = "ACTIVE"
        integrity = "INTACT" if linked_scenario else "UNKNOWN"
        recommendation = "HOLD"
        reasons = ["No deterministic degradation signal is active."]

    entry_origin = "UNKNOWN" if entry_record is None else entry_record["entry_origin"]
    return {
        "schema_version": "0.1.0",
        "review_id": sanitize_id(f"POSITION_REVIEW_{position['position_id']}_{snapshot_id}"),
        "position_id": position["position_id"],
        "snapshot_id": snapshot_id,
        "symbol": position["symbol"],
        "state": state,
        "entry_origin": entry_origin,
        "scenario_integrity": integrity,
        "progress_r": progress,
        "recommendation": recommendation,
        "manual_action_required": recommendation in {
            "PROTECT", "REDUCE_REVIEW", "EXIT_REVIEW", "MANUAL_RECONCILIATION_REQUIRED"
        },
        "reasons": reasons,
        "evidence_refs": market_packet["evidence_refs"],
    }
