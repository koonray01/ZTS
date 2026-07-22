from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_analysis_registry.backfill import backfill_eligible
from ctl_analysis_registry.paths import DEFAULT_WORKSPACE_CONFIG, load_registry_paths


def _object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Conservatively classify or append one legacy analysis decision.")
    parser.add_argument("--event", type=Path, required=True, help="Phase 1 event JSON")
    parser.add_argument("--source-bundle", type=Path, required=True, help="Pre-outcome source evidence JSON")
    parser.add_argument("--registry-config", type=Path, default=DEFAULT_WORKSPACE_CONFIG)
    parser.add_argument("--registry-root", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Classify without mutation (default)")
    mode.add_argument("--append-eligible", action="store_true", help="Explicitly append a supplied typed frozen decision")
    args = parser.parse_args(argv)
    paths = load_registry_paths(args.registry_config, registry_root=args.registry_root)
    result = backfill_eligible(
        _object(args.event), _object(args.source_bundle), paths.ledger,
        dry_run=not args.append_eligible, paths=paths,
    )
    print(json.dumps({**paths.metadata(), **result}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
