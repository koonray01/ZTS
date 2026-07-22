from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from ctl_analysis_registry.coordination import acquire_registry_writer
from ctl_analysis_registry.identity import stable_id
from ctl_analysis_registry.index import rebuild_index
from ctl_analysis_registry.paths import DEFAULT_WORKSPACE_CONFIG, load_registry_paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild the analysis registry SQLite read model.")
    parser.add_argument("--registry-config", type=Path, default=DEFAULT_WORKSPACE_CONFIG)
    parser.add_argument("--registry-root", type=Path)
    args = parser.parse_args(argv)
    paths = load_registry_paths(args.registry_config, registry_root=args.registry_root)
    now = datetime.now(timezone.utc)
    lease = acquire_registry_writer(paths, stable_id("REGISTRY_REBUILD", now.isoformat()), now)
    try:
        result = rebuild_index(paths.ledger, paths.sqlite)
    finally:
        lease.release()
    print(json.dumps({**paths.metadata(), **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
