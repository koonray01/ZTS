from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_mt5_snapshot import MetaTrader5SnapshotAdapter, SnapshotUnavailable, run_integration_harness  # noqa: E402


class TradingOSTFIRefreshError(RuntimeError):
    pass


def build_tradingos_tfi_provider(
    trading_os_root: str | Path,
    *,
    python_executable: str | None = None,
    timeframe: str = "M15",
    candles: int = 500,
    refresh_attempts: int = 2,
    command_timeout_seconds: float = 60,
    command_runner: Callable[..., Any] | None = None,
):
    root = Path(trading_os_root).resolve()
    entrypoint = root / "trade.py"
    latest = root / "data" / "tfi" / "snapshots" / "latest_snapshot.json"
    if not entrypoint.is_file():
        raise TradingOSTFIRefreshError(f"TradingOS entrypoint not found: {entrypoint}")
    runner = command_runner or subprocess.run
    executable = python_executable or sys.executable
    attempts = max(1, int(refresh_attempts))

    def run_command(action: str) -> None:
        command = [
            executable,
            str(entrypoint),
            "tfi",
            action,
            "--timeframe",
            timeframe,
        ]
        if action == "collect":
            command.extend(["--source", "mt5", "--candles", str(max(2, int(candles)))])
        completed = runner(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=command_timeout_seconds,
        )
        if completed.returncode != 0:
            detail = str(completed.stderr or completed.stdout or "TFI command failed").strip()
            raise TradingOSTFIRefreshError(f"TradingOS TFI {action} failed: {detail[-1000:]}")

    def validate_latest() -> None:
        try:
            packet = json.loads(latest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TradingOSTFIRefreshError(f"TradingOS TFI latest snapshot is unavailable: {latest}") from exc
        board = packet.get("market_board") if isinstance(packet.get("market_board"), list) else []
        if packet.get("execution_impact") != "none" or packet.get("can_execute") is not False:
            raise TradingOSTFIRefreshError("TradingOS TFI snapshot violates read-only safety invariants")
        if (packet.get("data_qc") or {}).get("status") != "PASS":
            raise TradingOSTFIRefreshError("TradingOS TFI snapshot QC is not PASS")
        if not board or any(str(item.get("quality", "UNKNOWN")).upper() != "FRESH" for item in board):
            raise TradingOSTFIRefreshError("TradingOS TFI snapshot does not have fresh synchronized tiles")
        if not packet.get("timestamp_utc") or not packet.get("evaluation_end_utc"):
            raise TradingOSTFIRefreshError("TradingOS TFI snapshot time binding is incomplete")

    def provider() -> str:
        last_error: Exception | None = None
        for _attempt in range(attempts):
            try:
                run_command("collect")
                run_command("analyze")
                validate_latest()
                return str(latest)
            except (OSError, subprocess.SubprocessError, TradingOSTFIRefreshError) as exc:
                last_error = exc
        raise TradingOSTFIRefreshError(f"TradingOS TFI refresh failed after {attempts} attempt(s): {last_error}")

    return provider


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
    parser.add_argument("--trading-os-root", help="TradingOS root used to refresh and attach read-only TFI before each snapshot.")
    parser.add_argument("--tfi-timeframe", default="M15")
    parser.add_argument("--tfi-candles", type=int, default=500)
    parser.add_argument("--tfi-refresh-attempts", type=int, default=2)
    parser.add_argument("--tfi-refresh-timeout-seconds", type=float, default=60)
    args = parser.parse_args()
    adapter = MetaTrader5SnapshotAdapter()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    tfi_provider = None
    if args.trading_os_root:
        tfi_provider = build_tradingos_tfi_provider(
            args.trading_os_root,
            timeframe=args.tfi_timeframe,
            candles=args.tfi_candles,
            refresh_attempts=args.tfi_refresh_attempts,
            command_timeout_seconds=args.tfi_refresh_timeout_seconds,
        )
    report = run_integration_harness(
        output_root=output,
        symbol=args.symbol,
        adapter=adapter,
        iterations=args.snapshots,
        run_id="RUN-SPRINT10-REAL-MT5",
        interval_seconds=args.interval_seconds,
        max_snapshot_elapsed_seconds=args.max_snapshot_seconds,
        tfi_shadow_source_provider=tfi_provider,
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
        "ready_candidate_count": report.get("ready_candidate_count", 0),
        "wait_candidate_count": report.get("wait_candidate_count", 0),
        "rejected_candidate_count": report.get("rejected_candidate_count", 0),
        "expired_candidate_count": report.get("expired_candidate_count", 0),
        "snapshots_without_candidate": report.get("snapshots_without_candidate", 0),
        "candidate_suppression_explained_ratio": report.get("candidate_suppression_explained_ratio"),
        "part3_requests": report.get("part3_requests", 0),
        "tfi_source_requested": report.get("tfi_source_requested", False),
        "tfi_context_attached_snapshots": report.get("tfi_context_attached_snapshots", 0),
        "tfi_context_observation_only_snapshots": report.get("tfi_context_observation_only_snapshots", 0),
        "tfi_context_unknown_snapshots": report.get("tfi_context_unknown_snapshots", 0),
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
