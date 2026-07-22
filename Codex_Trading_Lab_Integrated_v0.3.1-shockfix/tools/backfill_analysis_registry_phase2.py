from __future__ import annotations

import argparse
import json
from pathlib import Path

from ctl_analysis_registry.backfill import backfill_eligible


def _object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Conservatively classify or append one legacy analysis decision.")
    parser.add_argument("--event", type=Path, required=True, help="Phase 1 event JSON")
    parser.add_argument("--source-bundle", type=Path, required=True, help="Pre-outcome source evidence JSON")
    parser.add_argument("--ledger", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Classify without mutation (default)")
    mode.add_argument("--append-eligible", action="store_true", help="Explicitly append a supplied typed frozen decision")
    args = parser.parse_args()
    result = backfill_eligible(
        _object(args.event), _object(args.source_bundle), args.ledger,
        dry_run=not args.append_eligible,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
