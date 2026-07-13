from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .utils import iso_z, sanitize_id


def register_pending_plan(
    *,
    proposal: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "plan_id": sanitize_id(f"PENDING_PLAN_{proposal['proposal_id']}"),
        "candidate_id": proposal["candidate_id"],
        "snapshot_id": proposal["snapshot_id"],
        "symbol": proposal["symbol"],
        "side": proposal["side"],
        "entry_range": proposal["entry_range"],
        "invalidation": proposal["stop"],
        "expires_at": proposal["expires_at"],
        "status": "ACTIVE",
        "manual_only": True,
        "evidence_refs": proposal["evidence_refs"],
    }


def evaluate_pending_plan(
    plan: dict[str, Any],
    *,
    current_price: float,
    snapshot_time: datetime,
    position_filled_observed: bool = False,
) -> dict[str, Any]:
    updated = dict(plan)
    expiry = datetime.fromisoformat(plan["expires_at"].replace("Z", "+00:00")).astimezone(timezone.utc)

    if position_filled_observed:
        updated["status"] = "FILLED_OBSERVED"
        return updated
    if snapshot_time >= expiry:
        updated["status"] = "EXPIRED"
        return updated

    lower = float(plan["entry_range"]["lower"])
    upper = float(plan["entry_range"]["upper"])
    side = plan["side"]
    invalidation = float(plan["invalidation"])

    invalidated = current_price <= invalidation if side == "BUY" else current_price >= invalidation
    if invalidated:
        updated["status"] = "INVALIDATED"
    elif lower <= current_price <= upper:
        updated["status"] = "WINDOW_OPEN"
    else:
        moved_beyond = current_price > upper if side == "BUY" else current_price < lower
        if moved_beyond:
            updated["status"] = "CANCEL_RECOMMENDED"
        else:
            updated["status"] = "ACTIVE"
    return updated
