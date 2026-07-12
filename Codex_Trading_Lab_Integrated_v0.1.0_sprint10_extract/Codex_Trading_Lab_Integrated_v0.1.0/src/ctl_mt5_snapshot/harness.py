from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ctl_codex_worker import CodexWorker, ResultStore, ScriptedProvider, StateRegistry, WorkerJobStore
from ctl_codex_worker.audit import verify_journal
from ctl_codex_worker.job_store import verify_job_store
from ctl_codex_worker.result_store import verify_result_store
from ctl_decision_core import run_decision_core
from ctl_live_runtime import LiveRuntime
from ctl_permission_agent.jobs import build_codex_job

from .adapter import FixtureSnapshotAdapter, SnapshotAdapter
from .evidence import EvidenceStore
from .utils import iso_z, sanitize_id


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


def run_integration_harness(
    *,
    output_root: str | Path,
    symbol: str = "XAUUSD",
    adapter: SnapshotAdapter | None = None,
    iterations: int = 3,
    run_id: str = "RUN-SPRINT10-FIXTURE",
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
    opportunity_count = 0
    candidate_count = 0
    duplicate_suppression = 0
    worker_reports = []
    last_job_count = 0
    current_time = datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc)

    for index in range(iterations):
        if isinstance(adapter, FixtureSnapshotAdapter):
            adapter.capture_time = current_time + timedelta(minutes=5 * index, seconds=10)
        started = datetime.now(timezone.utc)
        snapshot = adapter.capture(symbol=symbol, run_id=sanitize_id(f"{run_id}_{index+1:03d}"), bars=30, include_h4=True)
        raw = evidence.write_raw_snapshot(snapshot)
        decision = run_decision_core(snapshot)
        evidence.write_normalized(snapshot=snapshot, name="decision_state", payload=decision, raw_sha256=raw.get("raw_sha256", "QUARANTINED"))
        runtime_report = runtime.process_snapshot(snapshot, now=current_time + timedelta(minutes=index))
        state = {**decision, "snapshot": snapshot}
        registry.put(snapshot["snapshot_id"], state)
        job = build_codex_job(
            snapshot_id=snapshot["snapshot_id"],
            event_types=["MARKET_STATE_CHANGED"] if index == 0 else ["SHOCK_DETECTED"] if index == iterations - 1 else ["STATE_REFRESH"],
            input_refs=[decision["market_packet"]["market_packet_id"], decision["scenario_packet"]["scenario_packet_id"], decision["entry_packet"]["entry_packet_id"]],
            now=current_time + timedelta(minutes=index),
        )
        inserted = worker_jobs.enqueue(job, now=current_time + timedelta(minutes=index))
        if not inserted:
            duplicate_suppression += 1
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
        worker_report = worker.run_once(now=current_time + timedelta(minutes=index))
        if worker_report:
            worker_reports.append(worker_report)
        opportunity_count += len(decision["scenario_packet"]["scenarios"])
        candidate_count += len(decision["entry_packet"]["candidates"])
        job_count = len(worker_jobs.project())
        if job_count == last_job_count:
            duplicate_suppression += 1
        last_job_count = job_count
        finished = datetime.now(timezone.utc)
        stage_timings.append({"snapshot_id": snapshot["snapshot_id"], "started_at": iso_z(started), "finished_at": iso_z(finished), "elapsed_ms": int((finished - started).total_seconds() * 1000)})
        snapshots.append({"snapshot_id": snapshot["snapshot_id"], "raw_status": raw["status"], "runtime_jobs": len(runtime_report["jobs_created"]), "worker_status": None if worker_report is None else worker_report["status"]})

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
        "snapshots": snapshots,
        "opportunity_count": opportunity_count,
        "candidate_count": candidate_count,
        "worker_result_count": len(worker_reports),
        "duplicate_suppression": duplicate_suppression,
        "stage_timings": stage_timings,
        "paused_position_monitoring_active": paused_state["position_monitoring_active"],
        "auto_execution_enabled": False,
        "trade_write_enabled": False,
        "part3_requests": 0,
        "order_actions": 0,
        "integrity": {"worker_job_store": job_ok, "worker_result_store": result_ok, "worker_audit": audit_ok, "errors": job_errors + result_errors + audit_errors},
        "final_decision": "GO_FOR_REAL_FORWARD_SHADOW" if adapter.source == "LIVE_MT5" else "CONDITIONAL_GO_PENDING_REAL_MT5",
    }
