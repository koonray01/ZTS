from __future__ import annotations

import argparse
import json
from pathlib import Path

from ctl_analysis_registry.verify import verify_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify analysis registry chain, index, coverage, and safety.")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--sqlite", type=Path)
    args = parser.parse_args()
    report = verify_registry(args.ledger, args.sqlite)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] in {"PASS", "CONDITIONAL"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
