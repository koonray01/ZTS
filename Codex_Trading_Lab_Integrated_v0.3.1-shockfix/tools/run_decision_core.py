from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402
from ctl_decision_core import run_decision_core  # noqa: E402


def validate(schema_name: str, payload: dict) -> list[str]:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [f"{error.json_path}: {error.message}" for error in validator.iter_errors(payload)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run detached Decision Core dry-run.")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", default="STANDARD")
    args = parser.parse_args()

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    result = run_decision_core(snapshot, profile=args.profile)
    errors = []
    errors.extend(validate("market_packet.schema.json", result["market_packet"]))
    errors.extend(validate("scenario.schema.json", result["scenario_packet"]))
    errors.extend(validate("entry_candidate.schema.json", result["entry_packet"]))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for key in ["basic_eyes", "advanced_eyes", "market_packet", "scenario_packet", "entry_packet"]:
        (output / f"{key}.json").write_text(json.dumps(result[key], indent=2), encoding="utf-8")
    (output / "current_action_plan.md").write_text(result["current_action_plan"], encoding="utf-8")
    summary = {
        "snapshot_id": result["snapshot_id"],
        "market_states": len(result["market_packet"]["market_state"]),
        "scenarios": len(result["scenario_packet"]["scenarios"]),
        "entry_candidates": len(result["entry_packet"]["candidates"]),
        "permission": result["execution_permission"],
        "output": str(output),
    }
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
