from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator  # noqa: E402
from ctl_replay_training import build_replay_intake  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an unlabeled LIVE_MT5 replay intake ledger.")
    parser.add_argument("--normalized-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--partition", default="FORWARD_SHADOW")
    parser.add_argument("--symbol", default="XAUUSD")
    args = parser.parse_args()
    report = build_replay_intake(args.normalized_root, partition=args.partition, symbol=args.symbol)
    schema = json.loads((ROOT / "schemas" / "replay_intake.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(report), key=lambda error: list(error.path))
    if errors:
        for error in errors:
            print(f"{error.json_path}: {error.message}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "mode": report["mode"],
        "source": report["source"],
        "snapshot_count": report["summary"]["snapshot_count"],
        "candidate_count": report["summary"]["candidate_count"],
        "ready_candidate_count": report["summary"]["ready_candidate_count"],
        "labeled_outcome_count": report["summary"]["labeled_outcome_count"],
        "readiness": report["readiness"],
        "output": str(args.output),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
