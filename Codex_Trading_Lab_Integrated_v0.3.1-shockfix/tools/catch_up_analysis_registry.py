from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ctl_analysis_registry.catchup import run_catchup
from ctl_mt5_snapshot.adapter import MetaTrader5SnapshotAdapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded read-only Analysis Registry outcome catch-up.")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--max-jobs", type=int, default=25)
    args = parser.parse_args()
    result = run_catchup(
        args.ledger, args.sqlite, args.evidence, MetaTrader5SnapshotAdapter(),
        datetime.now(timezone.utc), args.max_jobs,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"COMPLETE", "PARTIAL", "DEFERRED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
