from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_live_runtime import LiveRuntime  # noqa: E402
from ctl_live_runtime.provider import FixtureSequenceProvider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a detached live-runtime fixture sequence.")
    parser.add_argument("--snapshots", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    runtime = LiveRuntime(output, "XAUUSD")
    now = datetime(2025, 3, 3, 20, 0, 0, tzinfo=timezone.utc)
    runtime.start(now=now)

    reports = []
    for index, snapshot in enumerate(FixtureSequenceProvider(args.snapshots).snapshots(), start=1):
        report = runtime.process_snapshot(snapshot, now=now + timedelta(minutes=index))
        reports.append(
            {
                "snapshot_id": snapshot["snapshot_id"],
                "accepted_events": [
                    item["event_type"]
                    for item in report["watcher"]["accepted_significant_events"]
                ],
                "jobs_created": [job["job_id"] for job in report["jobs_created"]],
                "health": report["health"]["status"],
                "session_state": report["session"]["state"],
            }
        )

    runtime.stop(now=now + timedelta(minutes=10))
    summary = {
        "session_id": runtime.session.state["session_id"],
        "processed_snapshots": runtime.session.state["processed_snapshots"],
        "jobs_queued": runtime.queue.pending_count(),
        "final_state": runtime.session.state["state"],
        "reports": reports,
        "auto_execution_enabled": False,
    }
    (output / "session_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
