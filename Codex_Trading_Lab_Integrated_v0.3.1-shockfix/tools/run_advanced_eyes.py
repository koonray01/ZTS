from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402
from ctl_advanced_eyes import run_advanced_eyes  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Advanced Eyes against one immutable snapshot.")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeframes", default="")
    args = parser.parse_args()

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    selected = [item.strip() for item in args.timeframes.split(",") if item.strip()] or None
    envelope = run_advanced_eyes(snapshot, timeframes=selected)

    schema = json.loads((ROOT / "schemas" / "sensor_output.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = []
    for index, result in enumerate(envelope["results"]):
        for error in validator.iter_errors(result):
            errors.append(f"result[{index}] {error.json_path}: {error.message}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "snapshot_id": envelope["snapshot_id"],
                "results": envelope["summary"]["sensor_result_count"],
                "statuses": envelope["summary"]["status_counts"],
                "events": envelope["summary"]["event_counts"],
                "output": str(output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
