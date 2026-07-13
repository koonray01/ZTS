from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402
from ctl_replay_training.case import ReplayCase  # noqa: E402
from ctl_replay_training.runner import run_case  # noqa: E402


def validate(schema_name: str, payload: dict) -> list[str]:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    return [
        f"{error.json_path}: {error.message}"
        for error in Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(payload)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one blind replay case.")
    parser.add_argument("--case", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    case = ReplayCase.load(args.case)
    submission = json.loads(Path(args.decision).read_text(encoding="utf-8"))

    submission_errors = validate("trainee_decision.schema.json", submission)
    if submission_errors:
        print("\n".join(submission_errors), file=sys.stderr)
        return 2

    result = run_case(
        case=case,
        submission=submission,
        created_at=datetime(2025, 3, 4, 0, 0, tzinfo=timezone.utc),
    )
    score_errors = validate("replay_score.schema.json", result["score"])
    episode_errors = validate("replay_episode.schema.json", result["episode"])
    if score_errors or episode_errors:
        print("\n".join(score_errors + episode_errors), file=sys.stderr)
        return 3

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name in ["submission", "hidden_outcome", "score", "episode"]:
        (output / f"{name}.json").write_text(
            json.dumps(result[name], indent=2), encoding="utf-8"
        )
    visible = {
        "market_packet": result["observation"]["market_packet"],
        "scenario_packet": result["observation"]["scenario_packet"],
        "entry_packet": result["observation"]["entry_packet"],
    }
    (output / "visible_decision_state.json").write_text(
        json.dumps(visible, indent=2), encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "case_id": case.case_id,
                "partition": case.manifest["partition"],
                "total_score": result["score"]["total_score"],
                "deterministic_fail": result["score"]["deterministic_fail"],
                "outcome": result["score"]["outcome"]["classification"],
                "entry_engine_credit": result["score"]["entry_engine_credit"],
                "output": str(output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
