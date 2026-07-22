from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from ctl_analysis_registry.acceptance import worker_milestone_gate
from ctl_analysis_registry.paths import DEFAULT_WORKSPACE_CONFIG, load_registry_paths
from ctl_analysis_registry.worker import run_worker
from ctl_mt5_snapshot.adapter import MetaTrader5SnapshotAdapter


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the optional finite foreground Analysis Registry worker.")
    parser.add_argument("--registry-config", type=Path, default=DEFAULT_WORKSPACE_CONFIG)
    parser.add_argument("--registry-root", type=Path)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--max-jobs", type=int, default=25)
    args = parser.parse_args(argv)
    paths = load_registry_paths(args.registry_config, registry_root=args.registry_root)
    control_path = paths.root / "worker-control.json"
    stop_file = paths.root / "worker.stop"
    result = run_worker(
        {
            "ledger_path": paths.ledger, "sqlite_path": paths.sqlite,
            "evidence_root": paths.evidence, "adapter": MetaTrader5SnapshotAdapter(),
            "control_path": control_path, "cycles": args.cycles,
            "interval_seconds": args.interval_seconds, "max_jobs": args.max_jobs,
            "paths": paths,
        },
        stop_file,
    )
    print(json.dumps({**paths.metadata(), "worker_gate": worker_milestone_gate(result), **result}, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"COMPLETE", "PARTIAL", "DEFERRED", "STOPPED", "NOT_RUN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
