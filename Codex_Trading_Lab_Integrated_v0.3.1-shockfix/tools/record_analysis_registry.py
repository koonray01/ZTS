from __future__ import annotations

import argparse
import json
from pathlib import Path

from ctl_analysis_registry.ledger import AppendOnlyLedger
from ctl_analysis_registry.recorder import record_zenith_output


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a Zenith analysis output into the append-only registry.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--source-class", choices=["LIVE_MT5", "REPLAY", "SYNTHETIC", "CHAT_ONLY"])
    args = parser.parse_args()
    result = record_zenith_output(args.output_dir, AppendOnlyLedger(args.ledger), args.source_class)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
