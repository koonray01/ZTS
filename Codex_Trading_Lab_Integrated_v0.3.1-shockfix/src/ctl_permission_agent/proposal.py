from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .utils import sanitize_id


class ProposalNotAllowed(RuntimeError):
    pass


def build_manual_execution_proposal(
    *,
    decision: dict[str, Any],
    entry_packet: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if decision["decision"] != "APPROVED":
        raise ProposalNotAllowed(f"Part 3 decision is {decision['decision']}.")
    expiry = datetime.fromisoformat(decision["expires_at"].replace("Z", "+00:00"))
    if current_time >= expiry:
        raise ProposalNotAllowed("Part 3 approval has expired.")

    candidate = next(
        item for item in entry_packet["candidates"]
        if item["candidate_id"] == decision["candidate_id"]
    )
    return {
        "schema_version": "0.1.0",
        "proposal_id": sanitize_id(f"PROPOSAL_{decision['decision_id']}"),
        "decision_id": decision["decision_id"],
        "decision_hash": decision["decision_hash"],
        "snapshot_id": decision["snapshot_id"],
        "candidate_id": decision["candidate_id"],
        "symbol": decision["symbol"],
        "side": candidate["side"],
        "entry_range": candidate["entry_range"],
        "stop": candidate["stop"]["price"],
        "targets": [item["price"] for item in candidate["targets"]],
        "expires_at": decision["expires_at"],
        "manual_confirmation_required": True,
        "auto_execution_enabled": False,
        "warnings": [
            "Check current market price, spread and order details manually.",
            "Approval is invalid after expiry or any material market-state change.",
            "This proposal does not place, modify or cancel an order.",
        ],
        "evidence_refs": decision["evidence_refs"],
    }
