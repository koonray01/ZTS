from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ctl_codex_worker import CodexWorker, ResultStore, ScriptedProvider, StateRegistry, WorkerJobStore
from ctl_codex_worker.audit import verify_journal
from ctl_codex_worker.job_store import verify_job_store
from ctl_codex_worker.result_store import verify_result_store
from ctl_decision_core import run_decision_core
from ctl_live_runtime import LiveRuntime

from .adapter import FixtureSnapshotAdapter, SnapshotAdapter
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
    scenario_packet = decision["scenario_packet"]
    entry_packet = decision["entry_packet"]
    counts = {
        "NO_VALID_LOCATION": 0,
        "NO_ACTIVE_ZONE": 0,
        "TRIGGER_PENDING": 0,
        "RR_BELOW_MINIMUM": 0,
        "SHOCK_BLOCK": 0,
        "CONFLICT_BLOCK": 0,
        "STALE_OR_QC_BLOCK": 0,
        "SCENARIO_NOT_READY": 0,
        "LIMIT_NOT_ELIGIBLE": 0,
        "UNKNOWN_REQUIRED_INPUT": 0,
    }
    if market.get("freshness", {}).get("status") not in {None, "FRESH"}:
        counts["STALE_OR_QC_BLOCK"] += 1
    if any(flag.get("severity") == "BLOCK" for flag in market["risk_flags"]):
        counts["SHOCK_BLOCK"] += 1
    if market["conflicts"]:
        counts["CONFLICT_BLOCK"] += len(market["conflicts"])

    candidates_by_scenario: dict[str, list[dict[str, Any]]] = {}
    for candidate in entry_packet["candidates"]:
        candidates_by_scenario.setdefault(candidate["scenario_id"], []).append(candidate)
        if candidate["trigger"].get("status") == "PENDING":
            counts["TRIGGER_PENDING"] += 1
        if candidate["limit_eligibility"] not in {"NOT_APPLICABLE", "LIMIT_READY", "LIMIT_WATCH"}:
            counts["LIMIT_NOT_ELIGIBLE"] += 1
        for requirement in candidate["hard_requirements"]:
            if requirement["requirement_id"] == "MINIMUM_RR" and requirement["status"] == "FAIL":
                counts["RR_BELOW_MINIMUM"] += 1
            if requirement["requirement_id"] == "LOCATION" and requirement["status"] != "PASS":
                counts["NO_VALID_LOCATION"] += 1

    zones = market["active_zones"]
    for scenario in scenario_packet["scenarios"]:
        if scenario["scenario_id"] in candidates_by_scenario:
            continue
        if scenario["rank"] == "TAIL_RISK":
            counts["SHOCK_BLOCK"] += 1
        elif scenario["status"] not in {"ACTIVE", "WATCH"}:
            counts["SCENARIO_NOT_READY"] += 1
        elif not zones and "CONTINUATION" not in scenario["candidate_entry_types"]:
            counts["NO_ACTIVE_ZONE"] += 1
        elif scenario.get("missing_events"):
            counts["TRIGGER_PENDING"] += len(scenario["missing_events"])
        else:
            counts["UNKNOWN_REQUIRED_INPUT"] += 1

    return counts


def run_integration_harness(
    *,
    output_root: str | Path,
    symbol: str = "XAUUSD",
    adapter: SnapshotAdapter | None = None,
    iterations: int = 3,
    run_id: str = "RUN-SPRINT10-FIXTURE",
    interval_seconds: float = 0,
    max_snapshot_elapsed_seconds: float = 300,
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
        "TRIGGER_PENDING": 0,
        "RR_BELOW_MINIMUM": 0,
        "SHOCK_BLOCK": 0,
        "CONFLICT_BLOCK": 0,
        "STALE_OR_QC_BLOCK": 0,
        "SCENARIO_NOT_READY": 0,
        "LIMIT_NOT_ELIGIBLE": 0,
        "UNKNOWN_REQUIRED_INPUT": 0,
    }
    opportunity_count = 0
    candidate_count = 0
    worker_reports = []
    current_time = datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc) if isinstance(adapter, FixtureSnapshotAdapter) else datetime.now(timezone.utc)
    stopped_reason = None

    for index in range(iterations):
        if isinstance(adapter, FixtureSnapshotAdapter):
            adapter.capture_time = current_time + timedelta(minutes=5 * index, seconds=10)
            runtime_now = current_time + timedelta(minutes=index)
        else:
            runtime_now = datetime.now(timezone.utc)
        started = datetime.now(timezone.utc)
        snapshot = adapter.capture(symbol=symbol, run_id=sanitize_id(f"{run_id}_{index+1:03d}"), bars=30, include_h4=True)
        raw = evidence.write_raw_snapshot(snapshot)
        decision = run_decision_core(snapshot)
        market_hash = _market_state_hash(decision)
        market_hashes.append(market_hash)
        for reason, count in _candidate_suppression_breakdown(decision).items():
            candidate_suppression[reason] += count
        evidence.write_normalized(snapshot=snapshot, name="decision_state", payload=decision, raw_sha256=raw.get("raw_sha256", "QUARANTINED"))
        runtime_report = runtime.process_snapshot(snapshot, now=runtime_now)
        state = {**decision, "snapshot": snapshot}
        registry.put(snapshot["snapshot_id"], state)
        watcher = runtime_report["watcher"]
        significant_events += len(watcher["significant_events"])
        accepted_significant_events += len(watcher["accepted_significant_events"])
        jobs_created += len(runtime_report["jobs_created"])
        jobs_suppressed += max(0, len(watcher["significant_events"]) - len(watcher["accepted_significant_events"]))
        for job in runtime_report["jobs_created"]:
            inserted = worker_jobs.enqueue(job, now=runtime_now)
            if not inserted:
                jobs_suppressed += 1
        if runtime_report["jobs_created"]:
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
        opportunity_count += len(decision["scenario_packet"]["scenarios"])
        candidate_count += len(decision["entry_packet"]["candidates"])
        finished = datetime.now(timezone.utc)
        elapsed_seconds = (finished - started).total_seconds()
        stage_timings.append({"snapshot_id": snapshot["snapshot_id"], "started_at": iso_z(started), "finished_at": iso_z(finished), "elapsed_ms": int(elapsed_seconds * 1000)})
        snapshots.append({
            "snapshot_id": snapshot["snapshot_id"],
            "raw_status": raw["status"],
            "market_state_hash": market_hash,
            "significant_events": len(watcher["significant_events"]),
            "accepted_significant_events": len(watcher["accepted_significant_events"]),
            "runtime_jobs": len(runtime_report["jobs_created"]),
        })
        if elapsed_seconds > max_snapshot_elapsed_seconds:
            stopped_reason = f"SNAPSHOT_STAGE_TIMEOUT:{snapshot['snapshot_id']}:{elapsed_seconds:.3f}s"
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
        "candidate_count": candidate_count,
        "worker_result_count": len(worker_reports),
        "worker_invocations": len(worker_reports),
        "duplicate_event_ratio": 0.0 if significant_events == 0 else round((significant_events - accepted_significant_events) / significant_events, 6),
        "worker_invocations_per_unique_state": 0.0 if not market_hashes else round(len(worker_reports) / len(set(market_hashes)), 6),
        "candidate_suppression_breakdown": candidate_suppression,
        "stage_timings": stage_timings,
        "requested_snapshots": iterations,
        "completed_requested_snapshots": len(snapshots) == iterations,
        "stopped_reason": stopped_reason,
        "paused_position_monitoring_active": paused_state["position_monitoring_active"],
        "auto_execution_enabled": False,
        "trade_write_enabled": False,
        "part3_requests": 0,
        "order_actions": 0,
        "integrity": {"worker_job_store": job_ok, "worker_result_store": result_ok, "worker_audit": audit_ok, "errors": job_errors + result_errors + audit_errors},
        "final_decision": (
            "TIMED_SHADOW_INTERRUPTED_STALL" if stopped_reason
            else "GO_FOR_REAL_FORWARD_SHADOW" if adapter.source == "LIVE_MT5"
            else "CONDITIONAL_GO_PENDING_REAL_MT5"
        ),
    }
