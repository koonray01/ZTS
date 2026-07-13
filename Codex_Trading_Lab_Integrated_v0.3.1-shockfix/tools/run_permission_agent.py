from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402
from ctl_permission_agent import run_permission_agent_dry_run  # noqa: E402


def validate(schema_name: str, payload: dict) -> list[str]:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    return [
        f"{error.json_path}: {error.message}"
        for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run detached Permission & Agent dry-run.")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--account", default=str(ROOT / "examples" / "account_context.available.json"))
    parser.add_argument("--dependencies", default=str(ROOT / "examples" / "dependency_state.valid.json"))
    args = parser.parse_args()

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    account = json.loads(Path(args.account).read_text(encoding="utf-8"))
    dependencies = json.loads(Path(args.dependencies).read_text(encoding="utf-8"))
    result = run_permission_agent_dry_run(
        snapshot,
        account=account,
        dependency_state=dependencies,
        now=datetime(2025, 3, 3, 20, 0, 15, tzinfo=timezone.utc),
    )

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for key in ["market_packet", "scenario_packet", "entry_packet"]:
        (output / f"{key}.json").write_text(json.dumps(result[key], indent=2), encoding="utf-8")
    if result["part3_decision"] is not None:
        errors = validate("part3_decision.schema.json", result["part3_decision"])
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 2
        (output / "part3_decision.json").write_text(
            json.dumps(result["part3_decision"], indent=2), encoding="utf-8"
        )
    if result["manual_execution_proposal"] is not None:
        errors = validate("manual_execution_proposal.schema.json", result["manual_execution_proposal"])
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 2
        (output / "manual_execution_proposal.json").write_text(
            json.dumps(result["manual_execution_proposal"], indent=2), encoding="utf-8"
        )
    (output / "current_action_plan.md").write_text(result["current_action_plan"], encoding="utf-8")

    print(
        json.dumps(
            {
                "snapshot_id": result["snapshot_id"],
                "candidate_count": len(result["entry_packet"]["candidates"]),
                "part3_decision": None if result["part3_decision"] is None else result["part3_decision"]["decision"],
                "proposal_created": result["manual_execution_proposal"] is not None,
                "auto_execution_enabled": False,
                "output": str(output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
