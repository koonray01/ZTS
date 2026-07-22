from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_analysis_registry.paths import DEFAULT_WORKSPACE_CONFIG, RegistryPathError, load_registry_paths
from ctl_analysis_registry.verify import verify_registry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify analysis registry chain, index, coverage, and safety.")
    parser.add_argument("--registry-config", type=Path, default=DEFAULT_WORKSPACE_CONFIG)
    parser.add_argument("--registry-root", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--sqlite", type=Path)
    args = parser.parse_args(argv)
    paths = load_registry_paths(args.registry_config, registry_root=args.registry_root)
    ledger, sqlite = paths.ledger, paths.sqlite
    metadata = paths.metadata()
    if args.ledger is not None or args.sqlite is not None:
        if args.ledger is None:
            raise RegistryPathError("--ledger is required for explicit inspection")
        ledger = args.ledger.resolve()
        sqlite = args.sqlite.resolve() if args.sqlite is not None else None
        exact_canonical = ledger == paths.ledger and (sqlite is None or sqlite == paths.sqlite)
        if not exact_canonical:
            metadata = {**metadata, "registry_root": str(ledger.parent), "registry_mode": "NON_CANONICAL"}
    report = verify_registry(ledger, sqlite)
    print(json.dumps({**metadata, **report}, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] in {"PASS", "CONDITIONAL"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
