from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .gates import (
    gate_account_risk,
    gate_candidate_lifecycle,
    gate_dependencies,
    gate_duplicate,
    gate_evidence,
    gate_identity,
    gate_market_safety,
    gate_rr_invalidation,
    gate_snapshot,
    gate_trigger,
)
from .models import GateResult, Part3Context
from .policy import DEFAULT_RISK_POLICY
from .utils import evidence_union, iso_z, sanitize_id, sha256_json, utc_now


def _decision_from_gates(gates: list[GateResult]) -> str:
    statuses = {gate.status for gate in gates if gate.blocking}
    if "INVALID" in statuses:
        return "INVALIDATED"
    if "FAIL" in statuses:
        return "REJECTED"
    if "WAIT" in statuses:
        return "WAIT"
    return "APPROVED"


def run_part3(
    *,
    snapshot: dict[str, Any],
    market_packet: dict[str, Any],
    scenario_packet: dict[str, Any],
    entry_packet: dict[str, Any],
    candidate_id: str,
    account: dict[str, Any],
    dependency_state: dict[str, Any],
    risk_policy: dict[str, Any] | None = None,
    prior_decision_ids: set[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    policy = {**DEFAULT_RISK_POLICY, **(risk_policy or {})}
    current_time = (now or utc_now()).astimezone(timezone.utc)
    candidate = next(
        (item for item in entry_packet["candidates"] if item["candidate_id"] == candidate_id),
        None,
    )
    if candidate is None:
        raise KeyError(f"Unknown candidate_id: {candidate_id}")

    context = Part3Context(
        snapshot=snapshot,
        market_packet=market_packet,
        scenario_packet=scenario_packet,
        entry_packet=entry_packet,
        candidate=candidate,
        account=account,
        risk_policy=policy,
        dependency_state=dependency_state,
        prior_decision_ids=frozenset(prior_decision_ids or set()),
    )

    decision_seed = {
        "snapshot_id": snapshot["snapshot_id"],
        "candidate_id": candidate_id,
        "policy_version": policy["policy_version"],
        "account_context_id": account["account_context_id"],
    }
    decision_id = sanitize_id(
        f"PART3_{snapshot['snapshot_id']}_{candidate_id}_{sha256_json(decision_seed)[:12]}"
    )

    gates = [
        gate_identity(context),
        gate_snapshot(context),
        gate_candidate_lifecycle(context, current_time),
        gate_dependencies(context),
        gate_evidence(context),
        gate_trigger(context),
        gate_market_safety(context),
        gate_rr_invalidation(context),
        gate_account_risk(context),
        gate_duplicate(context, decision_id),
    ]
    decision = _decision_from_gates(gates)
    ttl = int(policy["approval_ttl_seconds"])
    expires_at = current_time + timedelta(seconds=ttl) if decision == "APPROVED" else None

    failed = [gate.gate_id for gate in gates if gate.status in {"FAIL", "INVALID"}]
    pending = [gate.gate_id for gate in gates if gate.status == "WAIT"]
    wait_for = [gate.message for gate in gates if gate.status == "WAIT"]
    prohibited = ["No auto execution.", "Do not reuse this decision for another snapshot or candidate."]
    if decision != "APPROVED":
        prohibited.insert(0, "Do not open a new trade from this candidate.")
    else:
        prohibited.insert(0, "Manual execution only after the user re-checks price and order details.")

    payload_without_hash = {
        "schema_version": "0.1.0",
        "decision_id": decision_id,
        "run_id": snapshot["run_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "candidate_id": candidate_id,
        "symbol": snapshot["symbol"],
        "decision": decision,
        "execution_scope": "MANUAL_ONLY",
        "issued_at": iso_z(current_time),
        "expires_at": iso_z(expires_at) if expires_at else None,
        "policy_version": policy["policy_version"],
        "account_context_id": account["account_context_id"],
        "gates": [gate.to_dict() for gate in gates],
        "failed_gates": failed,
        "pending_gates": pending,
        "what_to_wait_for": wait_for,
        "prohibited_actions": prohibited,
        "evidence_refs": evidence_union(snapshot, market_packet, scenario_packet, candidate),
    }
    decision_hash = sha256_json(payload_without_hash)
    return {
        **payload_without_hash,
        "decision_hash": decision_hash,
    }
