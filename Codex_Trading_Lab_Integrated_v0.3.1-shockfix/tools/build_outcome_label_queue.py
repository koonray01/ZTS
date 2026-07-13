from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator  # noqa: E402
from ctl_replay_training import build_outcome_label_queue  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an independent closed-bar outcome label queue.")
    parser.add_argument("--intake", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    intake = json.loads(args.intake.read_text(encoding="utf-8"))
    queue = build_outcome_label_queue(intake)
    schema = json.loads((ROOT / "schemas" / "replay_label_queue.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(queue), key=lambda error: list(error.path))
    if errors:
        for error in errors:
            print(f"{error.json_path}: {error.message}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(queue, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "readiness": queue["readiness"],
        "labelable_candidate_count": queue["summary"]["labelable_candidate_count"],
        "labeled_count": queue["summary"]["labeled_count"],
        "execution_permission_effect": queue["execution_permission_effect"],
        "output": str(args.output),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
