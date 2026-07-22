from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_analysis_registry.coordination import acquire_registry_writer
from ctl_analysis_registry.identity import stable_id
from ctl_analysis_registry.ledger import AppendOnlyLedger
from ctl_analysis_registry.paths import DEFAULT_WORKSPACE_CONFIG, load_registry_paths
from ctl_analysis_registry.recorder import record_zenith_output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record a Zenith analysis output into the append-only registry.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--registry-config", type=Path, default=DEFAULT_WORKSPACE_CONFIG)
    parser.add_argument("--registry-root", type=Path)
    parser.add_argument("--source-class", choices=["LIVE_MT5", "REPLAY", "SYNTHETIC", "CHAT_ONLY"])
    args = parser.parse_args(argv)
    paths = load_registry_paths(args.registry_config, registry_root=args.registry_root)
    now = datetime.now(timezone.utc)
    lease = acquire_registry_writer(paths, stable_id("REGISTRY_RECORD", str(args.output_dir.resolve()), now.isoformat()), now)
    try:
        result = record_zenith_output(args.output_dir, AppendOnlyLedger(paths.ledger), args.source_class)
    finally:
        lease.release()
    print(json.dumps({**paths.metadata(), **result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
