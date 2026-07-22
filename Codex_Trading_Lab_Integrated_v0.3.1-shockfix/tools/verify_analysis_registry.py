from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from ctl_analysis_registry.paths import DEFAULT_WORKSPACE_CONFIG, load_registry_paths
from ctl_analysis_registry.verify import verify_registry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify analysis registry chain, index, coverage, and safety.")
    parser.add_argument("--registry-config", type=Path, default=DEFAULT_WORKSPACE_CONFIG)
    parser.add_argument("--registry-root", type=Path)
    args = parser.parse_args(argv)
    paths = load_registry_paths(args.registry_config, registry_root=args.registry_root)
    report = verify_registry(paths.ledger, paths.sqlite)
    print(json.dumps({**paths.metadata(), **report}, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] in {"PASS", "CONDITIONAL"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
