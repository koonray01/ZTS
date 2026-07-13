from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_mt5_snapshot import EvidenceStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Bundle Sprint 10 evidence directory as a zip archive.")
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    archive = EvidenceStore(args.evidence_root).bundle(args.output)
    print(json.dumps({"archive": archive}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
