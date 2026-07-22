from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from ctl_analysis_registry.catchup import run_catchup
from ctl_analysis_registry.paths import DEFAULT_WORKSPACE_CONFIG, load_registry_paths
from ctl_mt5_snapshot.adapter import MetaTrader5SnapshotAdapter


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bounded read-only Analysis Registry outcome catch-up.")
    parser.add_argument("--registry-config", type=Path, default=DEFAULT_WORKSPACE_CONFIG)
    parser.add_argument("--registry-root", type=Path)
    parser.add_argument("--max-jobs", type=int, default=25)
    args = parser.parse_args(argv)
    paths = load_registry_paths(args.registry_config, registry_root=args.registry_root)
    result = run_catchup(
        ledger_path=paths.ledger, sqlite_path=paths.sqlite, evidence_root=paths.evidence,
        adapter=MetaTrader5SnapshotAdapter(), now=datetime.now(timezone.utc), max_jobs=args.max_jobs,
        paths=paths,
    )
    print(json.dumps({**paths.metadata(), **result}, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"COMPLETE", "PARTIAL", "DEFERRED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
