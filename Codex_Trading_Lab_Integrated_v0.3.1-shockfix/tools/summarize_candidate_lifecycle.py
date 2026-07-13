from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator  # noqa: E402
from ctl_replay_training import summarize_candidate_lifecycle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize semantic candidate lifecycle across snapshots.")
    parser.add_argument("--normalized-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = summarize_candidate_lifecycle(args.normalized_root)
    schema = json.loads((ROOT / "schemas" / "candidate_lifecycle.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(report), key=lambda error: list(error.path))
    if errors:
        for error in errors:
            print(f"{error.json_path}: {error.message}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "snapshots_analyzed": report["snapshots_analyzed"],
        "total_candidate_observations": report["total_candidate_observations"],
        "unique_candidate_count": report["unique_candidate_count"],
        "final_status_counts": report["final_status_counts"],
        "status_transition_counts": report["status_transition_counts"],
        "stable_wait_candidate_count": report["stable_wait_candidate_count"],
        "output": str(args.output),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
