from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_replay_training import summarize_candidate_quality  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize replay candidate quality; research QA only.")
    parser.add_argument("--results", nargs="+", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    records = []
    for result_dir in args.results:
        records.append(
            {
                "score": json.loads((result_dir / "score.json").read_text(encoding="utf-8")),
                "episode": json.loads((result_dir / "episode.json").read_text(encoding="utf-8")),
            }
        )
    report = summarize_candidate_quality(records)
    schema = json.loads((ROOT / "schemas" / "replay_calibration.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(report), key=lambda error: list(error.path))
    if errors:
        for error in errors:
            print(f"{error.json_path}: {error.message}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "calibration_status": report["calibration_status"],
        "total_episodes": report["coverage"]["total_episodes"],
        "credited_system_candidates": report["coverage"]["credited_system_candidates"],
        "resolved_system_candidates": report["coverage"]["resolved_system_candidates"],
        "trading_edge_established": report["trading_edge_established"],
        "output": str(args.output),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
