from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ctl_decision_core import run_decision_core

from .part3 import run_part3
from .policy import REQUIRED_DEPENDENCIES
from .proposal import ProposalNotAllowed, build_manual_execution_proposal


def run_permission_agent_dry_run(
    snapshot: dict[str, Any],
    *,
    account: dict[str, Any],
    dependency_state: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    decision_core = run_decision_core(snapshot)
    candidates = decision_core["entry_packet"]["candidates"]
    if not candidates:
        return {
            **decision_core,
            "part3_decision": None,
            "manual_execution_proposal": None,
        }

    preferred = next(
        (
            item for item in candidates
            if item["status"] == "READY_FOR_PERMISSION_REVIEW"
            and item["limit_eligibility"] == "LIMIT_READY"
        ),
        candidates[0],
    )
    decision = run_part3(
        snapshot=snapshot,
        market_packet=decision_core["market_packet"],
        scenario_packet=decision_core["scenario_packet"],
        entry_packet=decision_core["entry_packet"],
        candidate_id=preferred["candidate_id"],
        account=account,
        dependency_state=dependency_state or REQUIRED_DEPENDENCIES,
        now=now,
    )
    proposal = None
    if decision["decision"] == "APPROVED":
        proposal = build_manual_execution_proposal(
            decision=decision,
            entry_packet=decision_core["entry_packet"],
            now=now,
        )
    return {
        **decision_core,
        "snapshot": snapshot,
        "part3_decision": decision,
        "manual_execution_proposal": proposal,
    }
