from __future__ import annotations

import argparse
import json
from pathlib import Path

from ctl_analysis_registry.index import rebuild_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the analysis registry SQLite read model.")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--sqlite", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rebuild_index(args.ledger, args.sqlite), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
