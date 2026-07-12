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
    if report.get("snapshots_processed", 0) < 20:
        return "REAL_MT5_SMOKE_ONLY", False
    if report.get("order_actions") != 0:
        return "SAFETY_VIOLATION_ORDER_ACTIONS", False
    return "ACCEPTED_REAL_FORWARD_SHADOW_MINIMUM", True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real MT5 forward shadow validation without broker execution.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--snapshots", type=int, default=20)
    parser.add_argument("--interval-seconds", type=float, default=0)
    parser.add_argument("--max-snapshot-seconds", type=float, default=300)
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
        "unique_market_state_hashes": report["unique_market_state_hashes"],
        "jobs_created": report["jobs_created"],
        "jobs_suppressed": report["jobs_suppressed"],
        "worker_invocations": report["worker_invocations"],
        "order_actions": report["order_actions"],
        "trade_write_enabled": False,
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
