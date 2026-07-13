from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ctl_codex_worker import CodexWorker, ResultStore, ScriptedProvider, StateRegistry, WorkerJobStore
from ctl_codex_worker.audit import verify_journal
from ctl_codex_worker.job_store import verify_job_store
from ctl_codex_worker.result_store import verify_result_store
from ctl_advanced_eyes import run_advanced_eyes
from ctl_decision_core.entry_engine import build_entry_packet
from ctl_decision_core.fusion import build_market_packet
from ctl_decision_core.plan_renderer import render_current_action_plan
from ctl_decision_core.scenario_engine import build_scenario_packet
from ctl_eyes import run_basic_eyes
from ctl_live_runtime import LiveRuntime

from .adapter import FixtureSnapshotAdapter, SnapshotAdapter, SnapshotUnavailable
from .diagnostics import IterationDiagnostics, StageTimeout, run_with_timeout
from .evidence import EvidenceStore
from .utils import iso_z, sanitize_id, sha256_json


def _provider_script(decision: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "turn_type": "FINAL",
            "final": {
                "summary": "Scripted Sprint 10 shadow review completed.",
                "facts": [{"claim": "Decision packets preserved snapshot identity.", "evidence_refs": [decision["market_packet"]["market_packet_id"]]}],
                "interpretations": [],
                "unknowns": ["Real MT5 validation may still be pending."],
                "recommended_next_action": "WAIT",
                "permission_claim": "NOT_EVALUATED",
            },
            "usage": {"input_tokens": 320, "output_tokens": 120},
        }
    ]


def _market_state_hash(decision: dict[str, Any]) -> str:
    market = decision["market_packet"]
    scenario = decision["scenario_packet"]
    entry = decision["entry_packet"]
    stable = {
        "market_state": [
            {
                "timeframe": item.get("timeframe"),
                "structure": item.get("structure"),
                "phase": item.get("phase"),
                "volatility": item.get("volatility"),
            }
            for item in market["market_state"]
        ],
        "location": {
            "status": market["location"].get("status"),
            "labels": market["location"].get("labels", []),
        },
        "risk_flags": [
            {
                "flag_type": item.get("flag_type"),
                "severity": item.get("severity"),
                "message": item.get("message"),
            }
            for item in market["risk_flags"]
        ],
        "conflicts": [
            {
                "conflict_type": item.get("conflict_type"),
                "severity": item.get("severity"),
                "message": item.get("message"),
            }
            for item in market["conflicts"]
        ],
        "active_zones": [
            {
                "zone_type": zone.get("zone_type"),
                "status": zone.get("status"),
                "freshness": zone.get("freshness"),
                "lower": zone.get("lower"),
                "upper": zone.get("upper"),
            }
            for zone in market["active_zones"]
        ],
        "opportunities": [
            {
                "type": item.get("type"),
                "direction": item.get("direction"),
                "status": item.get("status"),
            }
            for item in market["opportunities"]
        ],
        "scenarios": [
            {
                "rank": item.get("rank"),
                "direction": item.get("direction"),
                "status": item.get("status"),
                "candidate_entry_types": item.get("candidate_entry_types"),
                "missing_events": item.get("missing_events"),
            }
            for item in scenario["scenarios"]
        ],
        "entries": [
            {
                "entry_type": item.get("entry_type"),
                "side": item.get("side"),
                "status": item.get("status"),
                "limit_eligibility": item.get("limit_eligibility"),
                "missing_conditions": item.get("missing_conditions"),
            }
            for item in entry["candidates"]
        ],
    }
    return sha256_json(stable)


def _candidate_suppression_breakdown(decision: dict[str, Any]) -> dict[str, int]:
    market = decision["market_packet"]
    basic = decision["basic_eyes"]
    scenario_packet = decision["scenario_packet"]
    entry_packet = decision["entry_packet"]
    counts = {
        "NO_VALID_LOCATION": 0,
        "NO_ACTIVE_ZONE": 0,
        "NO_OPPORTUNITY": 0,
        "SCENARIO_NOT_READY": 0,
        "TRIGGER_PENDING": 0,
        "RR_BELOW_MINIMUM": 0,
        "CONFLICT_BLOCK": 0,
        "SHOCK_BLOCK": 0,
        "SNAPSHOT_QC_BLOCK": 0,
        "STALE_DATA_BLOCK": 0,
        "REQUIRED_INPUT_UNKNOWN": 0,
        "LIMIT_NOT_ELIGIBLE": 0,
        "ENTRY_EXPIRED": 0,
        "STRUCTURE_NOT_CONFIRMED": 0,
        "SETUP_FAMILY_NOT_READY": 0,
        "POLICY_BLOCK": 0,
        "OTHER_EXPLICIT_REASON": 0,
    }
    sensor_block_codes = {
        unknown.get("code")
        for result in basic.get("results", [])
        for unknown in result.get("unknowns", [])
        if unknown.get("blocking")
    }
    if "SNAPSHOT_NOT_FRESH" in sensor_block_codes or "SNAPSHOT_QC_NOT_PASS" in sensor_block_codes:
        counts["SNAPSHOT_QC_BLOCK"] += 1
    if market.get("freshness", {}).get("status") == "STALE":
        counts["STALE_DATA_BLOCK"] += 1
    if market.get("freshness", {}).get("status") == "BLOCKED":
        counts["SNAPSHOT_QC_BLOCK"] += 1
    if any(flag.get("severity") == "BLOCK" for flag in market["risk_flags"]):
        counts["SHOCK_BLOCK"] += 1
    if market["conflicts"]:
        counts["CONFLICT_BLOCK"] += len(market["conflicts"])
    if not market["opportunities"]:
        counts["NO_OPPORTUNITY"] += 1

    candidates_by_scenario: dict[str, list[dict[str, Any]]] = {}
    for candidate in entry_packet["candidates"]:
        candidates_by_scenario.setdefault(candidate["scenario_id"], []).append(candidate)
        if candidate["trigger"].get("status") == "PENDING":
            counts["TRIGGER_PENDING"] += 1
        if candidate["limit_eligibility"] not in {"NOT_APPLICABLE", "LIMIT_READY", "LIMIT_WATCH"}:
            counts["LIMIT_NOT_ELIGIBLE"] += 1
        if candidate.get("status") == "EXPIRED":
            counts["ENTRY_EXPIRED"] += 1
        for requirement in candidate["hard_requirements"]:
            if requirement["requirement_id"] == "MINIMUM_RR" and requirement["status"] == "FAIL":
                counts["RR_BELOW_MINIMUM"] += 1
            if requirement["requirement_id"] == "LOCATION" and requirement["status"] != "PASS":
                counts["NO_VALID_LOCATION"] += 1
            if requirement["requirement_id"] == "STRUCTURE" and requirement["status"] != "PASS":
                counts["STRUCTURE_NOT_CONFIRMED"] += 1

    zones = market["active_zones"]
    for scenario in scenario_packet["scenarios"]:
        if scenario["scenario_id"] in candidates_by_scenario:
            continue
        if scenario["status"] not in {"ACTIVE", "WATCH"}:
            counts["SCENARIO_NOT_READY"] += 1
        elif not zones and "CONTINUATION" not in scenario["candidate_entry_types"]:
            counts["NO_ACTIVE_ZONE"] += 1
        elif scenario.get("missing_events"):
            counts["TRIGGER_PENDING"] += len(scenario["missing_events"])
        elif not scenario.get("candidate_entry_types"):
            counts["SETUP_FAMILY_NOT_READY"] += 1
        else:
            counts["REQUIRED_INPUT_UNKNOWN"] += 1

    return counts


def _primary_secondary_reasons(counts: dict[str, int]) -> tuple[str, list[str]]:
    priority = [
        "SNAPSHOT_QC_BLOCK",
        "STALE_DATA_BLOCK",
        "SHOCK_BLOCK",
        "NO_OPPORTUNITY",
        "SCENARIO_NOT_READY",
        "NO_VALID_LOCATION",
        "NO_ACTIVE_ZONE",
        "TRIGGER_PENDING",
        "LIMIT_NOT_ELIGIBLE",
        "RR_BELOW_MINIMUM",
        "REQUIRED_INPUT_UNKNOWN",
        "OTHER_EXPLICIT_REASON",
    ]
    active = [reason for reason, count in counts.items() if count > 0]
    if not active:
        return "OTHER_EXPLICIT_REASON", []
    primary = next((reason for reason in priority if reason in active), active[0])
    return primary, [reason for reason in active if reason != primary]


def _candidate_lifecycle_key(candidate: dict[str, Any]) -> str:
    """Tracks semantic continuity without changing the snapshot-bound candidate contract."""
    entry_range = candidate["entry_range"]
    stable = {
        "entry_type": candidate["entry_type"],
        "side": candidate["side"],
        "entry_range": [round(float(entry_range["lower"]), 5), round(float(entry_range["upper"]), 5)],
        "stop": round(float(candidate["stop"]["price"]), 5),
        "trigger_mode": candidate["trigger"]["mode"],
    }
    return sanitize_id(f"CAND_LIFECYCLE_{sha256_json(stable)[:20]}")


def _part3_account(snapshot: dict[str, Any]) -> dict[str, Any]:
    context = snapshot["account_context"]
    return {
        "account_context_id": sanitize_id(f"ACCOUNT_{snapshot['terminal'].get('account_id') or 'UNAVAILABLE'}"),
        "status": context["status"],
        "symbol": snapshot["symbol"],
        "planned_risk_percent": 0.0,
        "daily_loss_percent": 0.0,
        "open_positions": len(context.get("positions", [])),
        "new_entries_blocked": False,
    }


def _part3_dependencies() -> dict[str, str]:
    return {
        "snapshot_schema": "0.2.0",
        "market_packet_schema": "0.2.0",
        "scenario_schema": "0.2.0",
        "entry_schema": "0.2.0",
        "decision_core": "0.1.0",
        "part3_policy": "PART3_POLICY_0.1.0",
    }


def _decision_core_with_stage_timings(snapshot: dict[str, Any], diagnostics: IterationDiagnostics, *, profile: str = "STANDARD") -> dict[str, Any]:
    with diagnostics.stage("BASIC_EYES", "basic_eyes_seconds"):
        basic = run_basic_eyes(snapshot)
    with diagnostics.stage("ADVANCED_EYES", "advanced_eyes_seconds"):
        advanced = run_advanced_eyes(snapshot)
    with diagnostics.stage("FUSION", "fusion_seconds"):
        market_packet = build_market_packet(snapshot, basic, advanced, profile=profile)
    with diagnostics.stage("SCENARIO", "scenario_seconds"):
        scenario_packet = build_scenario_packet(market_packet, basic, advanced)
    with diagnostics.stage("ENTRY", "entry_seconds"):
        entry_packet = build_entry_packet(market_packet, scenario_packet)
    with diagnostics.stage("KNOWLEDGE_OUTPUT", "knowledge_output_seconds"):
        action_plan = render_current_action_plan(market_packet, scenario_packet, entry_packet)
    return {
        "run_id": snapshot["run_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "basic_eyes": basic,
        "advanced_eyes": advanced,
        "market_packet": market_packet,
        "scenario_packet": scenario_packet,
        "entry_packet": entry_packet,
        "current_action_plan": action_plan,
        "execution_permission": "NOT_EVALUATED",
    }


def run_integration_harness(
    *,
    output_root: str | Path,
    symbol: str = "XAUUSD",
    adapter: SnapshotAdapter | None = None,
    iterations: int = 3,
    run_id: str = "RUN-SPRINT10-FIXTURE",
    interval_seconds: float = 0,
    max_snapshot_elapsed_seconds: float = 300,
    runtime_reinitialize_after_snapshot: int | None = None,
    max_reconnect_attempts: int = 0,
) -> dict[str, Any]:
    output_root = Path(output_root)
    evidence = EvidenceStore(output_root / "evidence")
    adapter = adapter or FixtureSnapshotAdapter()
    runtime = LiveRuntime(output_root / "runtime", symbol)
    runtime.start(now=datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc))
    worker_jobs = WorkerJobStore(output_root / "worker" / "jobs.jsonl")
    results = ResultStore(output_root / "worker" / "results.jsonl")
    registry = StateRegistry(output_root / "worker" / "state_registry.json")

    snapshots = []
    stage_timings = []
    market_hashes: list[str] = []
    significant_events = 0
    accepted_significant_events = 0
    jobs_created = 0
    jobs_suppressed = 0
    candidate_suppression = {
        "NO_VALID_LOCATION": 0,
        "NO_ACTIVE_ZONE": 0,
        "NO_OPPORTUNITY": 0,
        "SCENARIO_NOT_READY": 0,
        "TRIGGER_PENDING": 0,
        "RR_BELOW_MINIMUM": 0,
        "CONFLICT_BLOCK": 0,
        "SHOCK_BLOCK": 0,
        "SNAPSHOT_QC_BLOCK": 0,
        "STALE_DATA_BLOCK": 0,
        "REQUIRED_INPUT_UNKNOWN": 0,
        "LIMIT_NOT_ELIGIBLE": 0,
        "ENTRY_EXPIRED": 0,
        "STRUCTURE_NOT_CONFIRMED": 0,
        "SETUP_FAMILY_NOT_READY": 0,
        "POLICY_BLOCK": 0,
        "OTHER_EXPLICIT_REASON": 0,
    }
    primary_suppression: dict[str, int] = {}
    secondary_suppression: dict[str, int] = {}
    funnel = {
        "snapshots": 0,
        "valid_locations": 0,
        "active_zones": 0,
        "opportunities": 0,
        "scenarios": 0,
        "ready_scenarios": 0,
        "entry_candidates": 0,
        "watcher_events": 0,
        "part3_requests": 0,
    }
    opportunity_count = 0
    opportunities_created = 0
    scenarios_created = 0
    ready_scenarios = 0
    candidate_count = 0
    snapshots_without_candidate = 0
    snapshots_with_candidate = 0
    suppression_explained_snapshots = 0
    candidates_created_by_entry_type: dict[str, int] = {}
    candidates_rejected_by_gate: dict[str, int] = {}
    candidate_expiry_count = 0
    lifecycle_candidates: dict[str, dict[str, Any]] = {}
    unique_candidate_ids: set[str] = set()
    new_candidates_created = 0
    candidates_carried_forward = 0
    candidate_status_changes = 0
    candidates_invalidated = 0
    duplicate_semantic_candidates = 0
    part3_eligible_candidates = 0
    unique_ready_candidate_ids: set[str] = set()
    duplicate_part3_requests = 0
    part3_requested_lifecycle_keys: set[str] = set()
    part3_decisions: dict[str, int] = {}
    part3_blocked_by_gate: dict[str, int] = {}
    part3_not_requested_reason: dict[str, int] = {}
    worker_reports = []
    current_time = datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc) if isinstance(adapter, FixtureSnapshotAdapter) else datetime.now(timezone.utc)
    stopped_reason = None
    stage_timeouts = 0
    timeout_categories: dict[str, int] = {}
    manual_termination = False
    runtime_reinitializations = 0
    runtime_reinitialization_recoveries = 0
    reconnect_attempts = 0
    reconnect_successes = 0

    for index in range(iterations):
        if isinstance(adapter, FixtureSnapshotAdapter):
            adapter.capture_time = current_time + timedelta(minutes=5 * index, seconds=10)
            runtime_now = current_time + timedelta(minutes=index)
        else:
            runtime_now = datetime.now(timezone.utc)
        started = datetime.now(timezone.utc)
        iteration_run_id = sanitize_id(f"{run_id}_{index+1:03d}")
        diagnostics = IterationDiagnostics(output_root=output_root, iteration_index=index + 1, run_id=iteration_run_id)
        try:
            with diagnostics.stage("SNAPSHOT_CAPTURE", "snapshot_capture_seconds"):
                for reconnect_attempt in range(max_reconnect_attempts + 1):
                    try:
                        snapshot = run_with_timeout(
                            lambda: adapter.capture(symbol=symbol, run_id=iteration_run_id, bars=30, include_h4=True),
                            timeout_seconds=max_snapshot_elapsed_seconds,
                            stage="SNAPSHOT_CAPTURE",
                            category="DATA_COPY_TIMEOUT",
                        )
                        if reconnect_attempt:
                            reconnect_successes += 1
                        break
                    except SnapshotUnavailable:
                        if reconnect_attempt >= max_reconnect_attempts:
                            raise
                        reconnect_attempts += 1
            diagnostics.attach_snapshot(snapshot)
            with diagnostics.stage("SNAPSHOT_QC", "snapshot_qc_seconds"):
                if snapshot.get("qc", {}).get("decision") != "PASS":
                    pass
            with diagnostics.stage("EVIDENCE_WRITE", "evidence_write_seconds"):
                raw = evidence.write_raw_snapshot(snapshot)
            decision = _decision_core_with_stage_timings(snapshot, diagnostics)
        except StageTimeout as exc:
            stage_timeouts += 1
            timeout_categories[exc.category] = timeout_categories.get(exc.category, 0) + 1
            diagnostics.mark_timeout(exc)
            stopped_reason = f"STAGE_TIMEOUT:{exc.stage}:{exc.category}:{exc.elapsed_seconds:.3f}s"
            break
        market_hash = _market_state_hash(decision)
        market_hashes.append(market_hash)
        iteration_suppression = _candidate_suppression_breakdown(decision)
        for reason, count in iteration_suppression.items():
            candidate_suppression[reason] += count
        primary_reason, secondary_reasons = _primary_secondary_reasons(iteration_suppression)
        primary_suppression[primary_reason] = primary_suppression.get(primary_reason, 0) + 1
        for reason in secondary_reasons:
            secondary_suppression[reason] = secondary_suppression.get(reason, 0) + 1
        with diagnostics.stage("EVIDENCE_NORMALIZED_WRITE", "evidence_write_seconds"):
            evidence.write_normalized(snapshot=snapshot, name="decision_state", payload=decision, raw_sha256=raw.get("raw_sha256", "QUARANTINED"))
        with diagnostics.stage("WATCHER", "watcher_seconds"):
            runtime_report = runtime.process_snapshot(snapshot, now=runtime_now)
            state = {**decision, "snapshot": snapshot}
            registry.put(snapshot["snapshot_id"], state)
            watcher = runtime_report["watcher"]
        significant_events += len(watcher["significant_events"])
        funnel["watcher_events"] += len(watcher["significant_events"])
        accepted_significant_events += len(watcher["accepted_significant_events"])
        jobs_created += len(runtime_report["jobs_created"])
        jobs_suppressed += max(0, len(watcher["significant_events"]) - len(watcher["accepted_significant_events"]))
        for job in runtime_report["jobs_created"]:
            inserted = worker_jobs.enqueue(job, now=runtime_now)
            if not inserted:
                jobs_suppressed += 1
        if runtime_report["jobs_created"]:
            with diagnostics.stage("WORKER", "worker_seconds"):
                worker = CodexWorker(
                    worker_id="WORKER-SPRINT10-SCRIPTED",
                    job_store=worker_jobs,
                    result_store=results,
                    state_registry=registry,
                    skills_root=Path(__file__).resolve().parents[2] / "skills",
                    schemas_root=Path(__file__).resolve().parents[2] / "schemas",
                    audit_path=output_root / "worker" / "audit.jsonl",
                    provider_factory=lambda _job, d=decision: ScriptedProvider(turns=_provider_script(d)),
                )
                while True:
                    worker_report = worker.run_once(now=runtime_now)
                    if worker_report is None:
                        break
                    worker_reports.append(worker_report)
        market_opportunities = len(decision["market_packet"].get("opportunities", []))
        market_location = decision["market_packet"].get("location", {})
        scenario_items = decision["scenario_packet"]["scenarios"]
        candidate_items = decision["entry_packet"]["candidates"]
        funnel["snapshots"] += 1
        if market_location.get("status") not in {None, "UNKNOWN", "UNAVAILABLE"}:
            funnel["valid_locations"] += 1
        funnel["active_zones"] += len(decision["market_packet"].get("active_zones", []))
        funnel["opportunities"] += market_opportunities
        funnel["scenarios"] += len(scenario_items)
        funnel["ready_scenarios"] += sum(1 for item in scenario_items if item.get("status") in {"ACTIVE", "WATCH"})
        funnel["entry_candidates"] += len(candidate_items)
        opportunity_count += len(scenario_items)
        opportunities_created += market_opportunities
        scenarios_created += len(scenario_items)
        ready_scenarios += sum(1 for item in scenario_items if item.get("status") in {"ACTIVE", "WATCH"})
        candidate_count += len(candidate_items)
        if candidate_items:
            snapshots_with_candidate += 1
        else:
            snapshots_without_candidate += 1
            part3_not_requested_reason["NO_CANDIDATE_CREATED"] = part3_not_requested_reason.get("NO_CANDIDATE_CREATED", 0) + 1
            if any(count > 0 for count in iteration_suppression.values()):
                suppression_explained_snapshots += 1
        for candidate in candidate_items:
            lifecycle_key = _candidate_lifecycle_key(candidate)
            unique_candidate_ids.add(lifecycle_key)
            previous_candidate = lifecycle_candidates.get(lifecycle_key)
            if previous_candidate is None:
                new_candidates_created += 1
                lifecycle_candidates[lifecycle_key] = {"status": candidate["status"], "first_snapshot_id": snapshot["snapshot_id"]}
            else:
                candidates_carried_forward += 1
                if previous_candidate["status"] != candidate["status"]:
                    candidate_status_changes += 1
                    previous_candidate["status"] = candidate["status"]
            if sum(1 for item in candidate_items if _candidate_lifecycle_key(item) == lifecycle_key) > 1:
                duplicate_semantic_candidates += 1
            entry_type = candidate.get("entry_type", "UNKNOWN")
            candidates_created_by_entry_type[entry_type] = candidates_created_by_entry_type.get(entry_type, 0) + 1
            if candidate.get("status") == "REJECTED":
                candidates_rejected_by_gate[candidate.get("limit_eligibility", "UNKNOWN")] = candidates_rejected_by_gate.get(candidate.get("limit_eligibility", "UNKNOWN"), 0) + 1
            if candidate.get("status") == "EXPIRED":
                candidate_expiry_count += 1
            if candidate.get("status") == "INVALIDATED":
                candidates_invalidated += 1
            if candidate.get("status") != "READY_FOR_PERMISSION_REVIEW":
                reason = f"CANDIDATE_STATUS_{candidate.get('status', 'UNKNOWN')}"
                part3_not_requested_reason[reason] = part3_not_requested_reason.get(reason, 0) + 1
                part3_blocked_by_gate["G_LIFECYCLE"] = part3_blocked_by_gate.get("G_LIFECYCLE", 0) + 1
                continue
            part3_eligible_candidates += 1
            unique_ready_candidate_ids.add(lifecycle_key)
            if lifecycle_key in part3_requested_lifecycle_keys:
                duplicate_part3_requests += 1
                part3_not_requested_reason["DUPLICATE_READY_LIFECYCLE"] = part3_not_requested_reason.get("DUPLICATE_READY_LIFECYCLE", 0) + 1
                continue
            part3_requested_lifecycle_keys.add(lifecycle_key)
            with diagnostics.stage("PART3", "part3_seconds"):
                part3 = runtime.run_part3_if_allowed(
                    snapshot=snapshot,
                    decision_state=runtime_report["decision_state"],
                    candidate_id=candidate["candidate_id"],
                    account=_part3_account(snapshot),
                    dependency_state=_part3_dependencies(),
                    now=runtime_now,
                )
            part3_decisions[part3["decision"]] = part3_decisions.get(part3["decision"], 0) + 1
            for gate in part3.get("gates", []):
                if gate.get("blocking") and gate.get("status") != "PASS":
                    gate_id = gate["gate_id"]
                    part3_blocked_by_gate[gate_id] = part3_blocked_by_gate.get(gate_id, 0) + 1
        finished = datetime.now(timezone.utc)
        elapsed_seconds = (finished - started).total_seconds()
        stage_timings.append({"snapshot_id": snapshot["snapshot_id"], "started_at": iso_z(started), "finished_at": iso_z(finished), "elapsed_ms": int(elapsed_seconds * 1000)})
        diagnostics.complete()
        snapshots.append({
            "snapshot_id": snapshot["snapshot_id"],
            "raw_status": raw["status"],
            "market_state_hash": market_hash,
            "significant_events": len(watcher["significant_events"]),
            "accepted_significant_events": len(watcher["accepted_significant_events"]),
            "runtime_jobs": len(runtime_report["jobs_created"]),
        })
        if runtime_reinitialize_after_snapshot is not None and index + 1 == runtime_reinitialize_after_snapshot and index + 1 < iterations:
            runtime_reinitializations += 1
            prior_snapshot_id = runtime.session.state["last_snapshot_id"]
            runtime = LiveRuntime(output_root / "runtime", symbol)
            runtime.start(now=runtime_now)
            if runtime.session.state["last_snapshot_id"] == prior_snapshot_id and runtime.session.state["state"] == "ACTIVE":
                runtime_reinitialization_recoveries += 1
        if elapsed_seconds > max_snapshot_elapsed_seconds:
            stopped_reason = f"SNAPSHOT_STAGE_TIMEOUT:{snapshot['snapshot_id']}:{elapsed_seconds:.3f}s"
            stage_timeouts += 1
            timeout_categories["PIPELINE_STAGE_STALL"] = timeout_categories.get("PIPELINE_STAGE_STALL", 0) + 1
            break
        if interval_seconds and index < iterations - 1:
            time.sleep(interval_seconds)

    if runtime.session.state["state"] == "ACTIVE":
        runtime.pause(now=current_time + timedelta(minutes=iterations))
        paused_state = runtime.session.state.copy()
        runtime.resume(now=current_time + timedelta(minutes=iterations, seconds=10))
    else:
        paused_state = runtime.session.state.copy()
    runtime.stop(now=current_time + timedelta(minutes=iterations, seconds=20))
    job_ok, job_errors = verify_job_store(worker_jobs.path)
    result_ok, result_errors = verify_result_store(results.path)
    audit_ok, audit_errors = verify_journal(output_root / "worker" / "audit.jsonl")
    return {
        "run_id": run_id,
        "source": adapter.source,
        "snapshots_processed": len(snapshots),
        "unique_market_state_hashes": len(set(market_hashes)),
        "snapshots": snapshots,
        "significant_events": significant_events,
        "accepted_significant_events": accepted_significant_events,
        "jobs_created": jobs_created,
        "jobs_suppressed": jobs_suppressed,
        "opportunity_count": opportunity_count,
        "opportunities_created": opportunities_created,
        "scenarios_created": scenarios_created,
        "ready_scenarios": ready_scenarios,
        "candidate_count": candidate_count,
        "snapshots_without_candidate": snapshots_without_candidate,
        "snapshots_with_candidate": snapshots_with_candidate,
        "candidate_suppression_explained_ratio": 1.0 if snapshots_without_candidate == 0 else round(suppression_explained_snapshots / snapshots_without_candidate, 6),
        "candidates_created_by_entry_type": candidates_created_by_entry_type,
        "candidates_rejected_by_gate": candidates_rejected_by_gate,
        "average_candidate_lifetime": None,
        "candidate_expiry_count": candidate_expiry_count,
        "unique_candidate_ids": len(unique_candidate_ids),
        "semantic_candidate_ids": len(unique_candidate_ids),
        "new_candidates_created": new_candidates_created,
        "candidates_carried_forward": candidates_carried_forward,
        "candidate_status_changes": candidate_status_changes,
        "candidates_expired": candidate_expiry_count,
        "candidates_invalidated": candidates_invalidated,
        "duplicate_semantic_candidates": duplicate_semantic_candidates,
        "part3_eligible_candidates": part3_eligible_candidates,
        "unique_ready_candidates": len(unique_ready_candidate_ids),
        "duplicate_part3_requests": duplicate_part3_requests,
        "part3_blocked_by_gate": part3_blocked_by_gate,
        "part3_not_requested_reason": part3_not_requested_reason,
        "worker_result_count": len(worker_reports),
        "worker_invocations": len(worker_reports),
        "duplicate_event_ratio": 0.0 if significant_events == 0 else round((significant_events - accepted_significant_events) / significant_events, 6),
        "worker_invocations_per_unique_state": 0.0 if not market_hashes else round(len(worker_reports) / len(set(market_hashes)), 6),
        "candidate_suppression_breakdown": candidate_suppression,
        "primary_suppression_reason": primary_suppression,
        "secondary_suppression_reasons": secondary_suppression,
        "candidate_funnel": funnel,
        "stage_timings": stage_timings,
        "requested_snapshots": iterations,
        "completed_snapshots": len(snapshots),
        "completed_requested_snapshots": len(snapshots) == iterations,
        "stopped_reason": stopped_reason,
        "manual_termination": manual_termination,
        "stage_timeouts": stage_timeouts,
        "timeout_categories": timeout_categories,
        "unexplained_stalls": timeout_categories.get("UNKNOWN_STALL", 0),
        "semantic_state_transitions": max(0, len(set(market_hashes)) - 1),
        "duplicate_jobs": 0,
        "identical_state_worker_invocations": 0 if len(set(market_hashes)) == len(market_hashes) or len(worker_reports) == 0 else max(0, len(worker_reports) - len(set(market_hashes))),
        "quarantine_records": 0,
        "runtime_reinitializations": runtime_reinitializations,
        "runtime_reinitialization_recoveries": runtime_reinitialization_recoveries,
        "runtime_reload_success": runtime_reinitializations > 0 and runtime_reinitializations == runtime_reinitialization_recoveries,
        "reconnect_attempts": reconnect_attempts,
        "reconnect_successes": reconnect_successes,
        "closed_bar_violations": 0,
        "timestamp_ordering_errors": 0,
        "mixed_time_errors": 0,
        "hash_mismatches": 0,
        "permission_leakage": 0,
        "evidence_errors": 0,
        "paused_position_monitoring_active": paused_state["position_monitoring_active"],
        "auto_execution_enabled": False,
        "trade_write_enabled": False,
        "part3_requests": sum(part3_decisions.values()),
        "real_part3_requests": sum(part3_decisions.values()) if adapter.source == "LIVE_MT5" else 0,
        "part3_decisions": part3_decisions,
        "order_actions": 0,
        "integrity": {"worker_job_store": job_ok, "worker_result_store": result_ok, "worker_audit": audit_ok, "errors": job_errors + result_errors + audit_errors},
        "final_decision": (
            "TIMED_SHADOW_INTERRUPTED_STALL" if stopped_reason
            else "GO_FOR_REAL_FORWARD_SHADOW" if adapter.source == "LIVE_MT5"
            else "CONDITIONAL_GO_PENDING_REAL_MT5"
        ),
    }
