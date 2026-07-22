from __future__ import annotations

import argparse
import json
from pathlib import Path

from ctl_analysis_registry.worker import run_worker
from ctl_mt5_snapshot.adapter import MetaTrader5SnapshotAdapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the optional finite foreground Analysis Registry worker.")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--stop-file", type=Path, required=True)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--max-jobs", type=int, default=25)
    args = parser.parse_args()
    result = run_worker(
        {
            "ledger_path": args.ledger, "sqlite_path": args.sqlite,
            "evidence_root": args.evidence, "adapter": MetaTrader5SnapshotAdapter(),
            "control_path": args.control, "cycles": args.cycles,
            "interval_seconds": args.interval_seconds, "max_jobs": args.max_jobs,
        },
        args.stop_file,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"COMPLETE", "PARTIAL", "DEFERRED", "STOPPED", "NOT_RUN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
