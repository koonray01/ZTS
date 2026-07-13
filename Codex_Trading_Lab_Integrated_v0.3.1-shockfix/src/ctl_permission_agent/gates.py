from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .dependency_guard import check_dependencies
from .models import GateResult, Part3Context
from .utils import evidence_union


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def gate_identity(context: Part3Context) -> GateResult:
    candidate = context.candidate
    identifiers = {
        context.snapshot["run_id"],
        context.market_packet["run_id"],
        context.scenario_packet["run_id"],
        context.entry_packet["run_id"],
    }
    snapshots = {
        context.snapshot["snapshot_id"],
        context.market_packet["snapshot_id"],
        context.scenario_packet["snapshot_id"],
        context.entry_packet["snapshot_id"],
    }
    candidate_ids = {item["candidate_id"] for item in context.entry_packet["candidates"]}
    if len(identifiers) != 1 or len(snapshots) != 1:
        return GateResult("G_IDENTITY", "INVALID", "Mixed run or snapshot identity.", True)
    if candidate["candidate_id"] not in candidate_ids:
        return GateResult("G_IDENTITY", "INVALID", "Candidate is not in the supplied entry packet.", True)
    if candidate["scenario_id"] not in {item["scenario_id"] for item in context.scenario_packet["scenarios"]}:
        return GateResult("G_IDENTITY", "INVALID", "Candidate scenario is not in the scenario packet.", True)
    return GateResult(
        "G_IDENTITY",
        "PASS",
        "Run, snapshot, scenario and candidate identities match.",
        False,
        tuple(evidence_union(candidate)),
    )


def gate_snapshot(context: Part3Context) -> GateResult:
    freshness = context.snapshot["freshness"]["status"]
    qc = context.snapshot["qc"]["decision"]
    if freshness != "FRESH":
        return GateResult("G_SNAPSHOT", "WAIT", f"Fresh snapshot required; got {freshness}.", True)
    if qc != "PASS":
        return GateResult("G_SNAPSHOT", "WAIT", f"Snapshot QC must pass; got {qc}.", True)
    if context.market_packet["permission_state"] != "NOT_EVALUATED":
        return GateResult("G_SNAPSHOT", "INVALID", "Unexpected permission already embedded in market packet.", True)
    return GateResult(
        "G_SNAPSHOT",
        "PASS",
        "Snapshot is fresh and QC passed.",
        False,
        tuple(context.snapshot.get("evidence_refs", [])),
    )


def gate_candidate_lifecycle(context: Part3Context, now: datetime) -> GateResult:
    candidate = context.candidate
    status = candidate["status"]
    if status in {"INVALIDATED", "EXPIRED"}:
        return GateResult("G_LIFECYCLE", "INVALID", f"Candidate is {status}.", True)
    if status == "REJECTED":
        return GateResult("G_LIFECYCLE", "FAIL", "Candidate was rejected upstream.", True)

    expiry = candidate["expiry"]
    expires_at = _parse_time(expiry.get("expires_at"))
    if expires_at is not None and now >= expires_at:
        return GateResult("G_LIFECYCLE", "INVALID", "Candidate expiry time has passed.", True)
    bars_remaining = expiry.get("bars_remaining")
    if bars_remaining is not None and bars_remaining <= 0:
        return GateResult("G_LIFECYCLE", "INVALID", "Candidate has no bars remaining.", True)

    if status == "WAIT":
        return GateResult("G_LIFECYCLE", "WAIT", "Candidate is still waiting for its entry condition.", True)
    if status != "READY_FOR_PERMISSION_REVIEW":
        return GateResult("G_LIFECYCLE", "WAIT", f"Unsupported ready state: {status}.", True)
    return GateResult("G_LIFECYCLE", "PASS", "Candidate is active and ready for Part 3 review.", False)


def gate_dependencies(context: Part3Context) -> GateResult:
    return check_dependencies(context.dependency_state)


def gate_evidence(context: Part3Context) -> GateResult:
    refs = evidence_union(
        context.snapshot.get("evidence_refs", []),
        context.market_packet,
        context.scenario_packet,
        context.candidate,
    )
    if not refs:
        return GateResult("G_EVIDENCE", "INVALID", "No evidence references are attached.", True)
    if any(item.get("blocking") for item in context.market_packet.get("unknowns", [])):
        blocking = [item["code"] for item in context.market_packet["unknowns"] if item.get("blocking")]
        return GateResult(
            "G_EVIDENCE",
            "WAIT",
            "Blocking unknowns remain: " + ", ".join(blocking),
            True,
            tuple(refs),
        )
    return GateResult("G_EVIDENCE", "PASS", "Evidence references exist and no blocking unknown remains.", False, tuple(refs))


def gate_trigger(context: Part3Context) -> GateResult:
    candidate = context.candidate
    entry_type = candidate["entry_type"]
    trigger = candidate["trigger"]
    if entry_type == "STRUCTURED_LIMIT":
        if not context.risk_policy.get("allow_structured_limit", False):
            return GateResult("G_TRIGGER", "FAIL", "Structured limits are disabled by policy.", True)
        if candidate["limit_eligibility"] != "LIMIT_READY":
            return GateResult(
                "G_TRIGGER",
                "WAIT",
                f"Structured limit is {candidate['limit_eligibility']}.",
                True,
            )
        return GateResult("G_TRIGGER", "PASS", "Structured limit eligibility is ready.", False)

    if trigger["status"] != "SATISFIED":
        missing = ", ".join(candidate.get("missing_conditions", [])) or "trigger sequence"
        return GateResult("G_TRIGGER", "WAIT", f"Trigger is pending: {missing}.", True)
    return GateResult("G_TRIGGER", "PASS", "Required trigger sequence is satisfied.", False)


def gate_market_safety(context: Part3Context) -> GateResult:
    blocking_flags = [item["code"] for item in context.market_packet["risk_flags"] if item["severity"] == "BLOCK"]
    blocking_conflicts = [item["conflict_id"] for item in context.market_packet["conflicts"] if item["blocking"]]
    if blocking_flags:
        return GateResult(
            "G_MARKET_SAFETY",
            "WAIT",
            "Blocking market risk: " + ", ".join(blocking_flags),
            True,
            tuple(context.market_packet["evidence_refs"]),
        )
    if blocking_conflicts:
        return GateResult(
            "G_MARKET_SAFETY",
            "WAIT",
            "Blocking market conflict: " + ", ".join(blocking_conflicts),
            True,
        )
    return GateResult("G_MARKET_SAFETY", "PASS", "No blocking market risk or conflict.", False)


def gate_rr_invalidation(context: Part3Context) -> GateResult:
    candidate = context.candidate
    rr = candidate["rr"]["to_first_target"]
    minimum = max(context.risk_policy["minimum_rr"], candidate["rr"]["minimum"])
    side = candidate["side"]
    entry_mid = (candidate["entry_range"]["lower"] + candidate["entry_range"]["upper"]) / 2.0
    stop = candidate["stop"]["price"]
    valid_stop = stop < entry_mid if side == "BUY" else stop > entry_mid
    if not valid_stop:
        return GateResult("G_RR_INVALIDATION", "INVALID", "Stop is on the wrong side of entry.", True)
    if rr < minimum:
        return GateResult(
            "G_RR_INVALIDATION",
            "FAIL",
            f"RR {rr:.2f} is below required {minimum:.2f}.",
            True,
        )
    if candidate["invalidation"]["level"] is None:
        return GateResult("G_RR_INVALIDATION", "WAIT", "Structural invalidation level is missing.", True)
    return GateResult(
        "G_RR_INVALIDATION",
        "PASS",
        f"RR {rr:.2f} and structural invalidation pass.",
        False,
        tuple(candidate["invalidation"]["evidence_refs"]),
    )


def gate_account_risk(context: Part3Context) -> GateResult:
    account = context.account
    policy = context.risk_policy
    if account.get("status") != "AVAILABLE":
        return GateResult("G_ACCOUNT_RISK", "WAIT", "Account and risk context are unavailable.", True)
    if account.get("new_entries_blocked"):
        return GateResult("G_ACCOUNT_RISK", "FAIL", "New entries are blocked by account state.", True)
    if float(account.get("planned_risk_percent", 0.0)) > float(policy["maximum_risk_percent"]):
        return GateResult(
            "G_ACCOUNT_RISK",
            "FAIL",
            "Planned risk exceeds maximum risk per trade.",
            True,
        )
    if float(account.get("daily_loss_percent", 0.0)) >= float(policy["maximum_daily_loss_percent"]):
        return GateResult("G_ACCOUNT_RISK", "FAIL", "Daily loss limit reached.", True)
    if int(account.get("open_positions", 0)) >= int(policy["maximum_open_positions"]):
        return GateResult("G_ACCOUNT_RISK", "FAIL", "Maximum open positions reached.", True)
    if account.get("symbol") not in {None, context.market_packet["symbol"]}:
        return GateResult("G_ACCOUNT_RISK", "INVALID", "Account risk context symbol mismatch.", True)
    return GateResult("G_ACCOUNT_RISK", "PASS", "Account and risk budget pass.", False)


def gate_duplicate(context: Part3Context, decision_id: str) -> GateResult:
    if decision_id in context.prior_decision_ids:
        return GateResult("G_DUPLICATE", "FAIL", "Duplicate Part 3 decision ID.", True)
    return GateResult("G_DUPLICATE", "PASS", "Decision ID is new.", False)
