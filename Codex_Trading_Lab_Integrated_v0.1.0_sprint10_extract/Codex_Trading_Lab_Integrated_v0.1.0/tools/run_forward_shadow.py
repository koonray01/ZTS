from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_mt5_snapshot import MetaTrader5SnapshotAdapter, SnapshotUnavailable, run_integration_harness  # noqa: E402


def classify_acceptance(report: dict) -> tuple[str, bool]:
    if report.get("stopped_reason"):
        return "TIMED_SHADOW_INTERRUPTED_STALL", False
    if report.get("source") != "LIVE_MT5":
        return "REAL_MT5_VALIDATION_PENDING", False
    if not report.get("completed_requested_snapshots"):
        return "INCOMPLETE_REQUESTED_SNAPSHOTS", False
    if report.get("stage_timeouts", 0) != 0:
        return "STAGE_TIMEOUT_DETECTED", False
    if report.get("unexplained_stalls", 0) != 0:
        return "UNEXPLAINED_STALL_DETECTED", False
    if report.get("order_actions") != 0:
        return "SAFETY_VIOLATION_ORDER_ACTIONS", False
    if report.get("requested_snapshots") == 10 and report.get("snapshots_processed") == 10:
        return "TIMED_CANARY_PASS", True
    if report.get("requested_snapshots") == 120 and report.get("snapshots_processed") == 120:
        return "TIMED_FORWARD_SHADOW_PASS", True
    if report.get("snapshots_processed", 0) < 20:
        return "REAL_MT5_SMOKE_ONLY", False
    return "ACCEPTED_REAL_FORWARD_SHADOW_MINIMUM", True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real MT5 forward shadow validation without broker execution.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--snapshots", type=int, default=20)
    parser.add_argument("--interval-seconds", type=float, default=0)
    parser.add_argument("--max-snapshot-seconds", type=float, default=300)
    parser.add_argument("--runtime-reinitialize-after-snapshot", type=int)
    parser.add_argument("--max-reconnect-attempts", type=int, default=0)
    args = parser.parse_args()
    adapter = MetaTrader5SnapshotAdapter()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    report = run_integration_harness(
        output_root=output,
        symbol=args.symbol,
        adapter=adapter,
        iterations=args.snapshots,
        run_id="RUN-SPRINT10-REAL-MT5",
        interval_seconds=args.interval_seconds,
        max_snapshot_elapsed_seconds=args.max_snapshot_seconds,
        runtime_reinitialize_after_snapshot=args.runtime_reinitialize_after_snapshot,
        max_reconnect_attempts=args.max_reconnect_attempts,
    )
    (output / "forward_shadow_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    acceptance_status, accepted = classify_acceptance(report)
    print(json.dumps({
        "harness_decision": report["final_decision"],
        "acceptance_status": acceptance_status,
        "accepted": accepted,
        "snapshots_processed": report["snapshots_processed"],
        "requested_snapshots": report["requested_snapshots"],
        "completed_requested_snapshots": report["completed_requested_snapshots"],
        "stopped_reason": report["stopped_reason"],
        "manual_termination": report.get("manual_termination", False),
        "stage_timeouts": report.get("stage_timeouts", 0),
        "unexplained_stalls": report.get("unexplained_stalls", 0),
        "unique_market_state_hashes": report["unique_market_state_hashes"],
        "semantic_state_transitions": report.get("semantic_state_transitions", 0),
        "significant_events": report.get("significant_events", 0),
        "jobs_created": report["jobs_created"],
        "jobs_suppressed": report["jobs_suppressed"],
        "duplicate_jobs": report.get("duplicate_jobs", 0),
        "worker_invocations": report["worker_invocations"],
        "identical_state_worker_invocations": report.get("identical_state_worker_invocations", 0),
        "candidate_count": report.get("candidate_count", 0),
        "unique_candidate_ids": report.get("unique_candidate_ids", 0),
        "new_candidates_created": report.get("new_candidates_created", 0),
        "candidates_carried_forward": report.get("candidates_carried_forward", 0),
        "candidate_status_changes": report.get("candidate_status_changes", 0),
        "candidates_expired": report.get("candidates_expired", 0),
        "candidates_invalidated": report.get("candidates_invalidated", 0),
        "duplicate_semantic_candidates": report.get("duplicate_semantic_candidates", 0),
        "part3_eligible_candidates": report.get("part3_eligible_candidates", 0),
        "part3_blocked_by_gate": report.get("part3_blocked_by_gate", {}),
        "part3_not_requested_reason": report.get("part3_not_requested_reason", {}),
        "snapshots_without_candidate": report.get("snapshots_without_candidate", 0),
        "candidate_suppression_explained_ratio": report.get("candidate_suppression_explained_ratio"),
        "part3_requests": report.get("part3_requests", 0),
        "part3_decisions": report.get("part3_decisions", {}),
        "runtime_reinitializations": report.get("runtime_reinitializations", 0),
        "runtime_reinitialization_recoveries": report.get("runtime_reinitialization_recoveries", 0),
        "reconnect_attempts": report.get("reconnect_attempts", 0),
        "reconnect_successes": report.get("reconnect_successes", 0),
        "order_actions": report["order_actions"],
        "permission_leakage": report.get("permission_leakage", 0),
        "queue_errors": 0 if report.get("integrity", {}).get("worker_job_store") else 1,
        "audit_errors": 0 if report.get("integrity", {}).get("worker_audit") else 1,
        "trade_write_enabled": False,
        "auto_execution_enabled": False,
    }))
    return 0 if accepted else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SnapshotUnavailable as exc:
        print(json.dumps({"status": "REAL_MT5_VALIDATION_PENDING", "message": str(exc), "fallback_used": False}), file=sys.stderr)
        raise SystemExit(3)
    except Exception as exc:
        print(json.dumps({"status": "REAL_MT5_VALIDATION_PENDING", "error_type": type(exc).__name__, "message": str(exc), "fallback_used": False}), file=sys.stderr)
        raise SystemExit(3)
