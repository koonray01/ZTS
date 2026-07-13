from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402
from ctl_replay_training.case import ReplayCase  # noqa: E402
from ctl_replay_training.runner import run_case  # noqa: E402
from ctl_knowledge_learning.orchestrator import run_knowledge_cycle  # noqa: E402


def validate(schema_name: str, payload: dict) -> list[str]:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    return [
        f"{error.json_path}: {error.message}"
        for error in Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(payload)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a detached replay-to-learning cycle.")
    parser.add_argument("--cases-root", required=True)
    parser.add_argument("--decisions-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    case_decisions = [
        ("bullish_continuation", "bullish_continuation.correct.json"),
        ("shock_no_trade", "shock_no_trade.correct.json"),
        ("ambiguous_same_bar", "ambiguous_same_bar.correct.json"),
    ]
    replay_results = []
    for case_folder, decision_name in case_decisions:
        case = ReplayCase.load(Path(args.cases_root) / case_folder)
        decision = json.loads(
            (Path(args.decisions_root) / decision_name).read_text(encoding="utf-8")
        )
        replay_results.append(
            run_case(
                case=case,
                submission=decision,
                created_at=datetime(2025, 3, 5, 0, 0, tzinfo=timezone.utc),
            )
        )

    # Demonstration-only repeated process failures. These remain REPLAY records and
    # create an Observation/Hypothesis, never a production rule.
    bad_base = json.loads(
        (Path(args.decisions_root) / "future_leak.invalid.json").read_text(
            encoding="utf-8"
        )
    )
    bad_case = ReplayCase.load(Path(args.cases_root) / "bullish_continuation")
    for index in range(3):
        bad_decision = copy.deepcopy(bad_base)
        bad_decision["submission_id"] = f"SUB-CLI-FUTURE-LEAK-{index+1}"
        replay_results.append(
            run_case(
                case=bad_case,
                submission=bad_decision,
                created_at=datetime(
                    2025, 3, 5, 0, index + 1, tzinfo=timezone.utc
                ),
            )
        )

    output = Path(args.output)
    result = run_knowledge_cycle(
        root=output,
        replay_results=replay_results,
        created_at=datetime(2025, 3, 5, 0, 0, tzinfo=timezone.utc),
    )

    errors = validate("learning_report.schema.json", result["learning_report"])
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2

    (output / "learning_report.json").write_text(
        json.dumps(result["learning_report"], indent=2), encoding="utf-8"
    )
    (output / "knowledge_snapshot.json").write_text(
        json.dumps(result["knowledge_snapshot"], indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "episodes_ingested": len(result["ingested_episode_records"]),
                "observations_created": len(
                    result["learning_report"]["observations_created"]
                ),
                "hypotheses_created": len(
                    result["learning_report"]["hypotheses_created"]
                ),
                "edge_status": result["learning_report"]["edge_status"],
                "production_policy_changed": False,
                "output": str(output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
