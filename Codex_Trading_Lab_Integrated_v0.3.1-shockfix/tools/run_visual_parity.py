from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_visual_parity import compare_visual_observation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare a metadata-bound visual observation with a market packet.")
    parser.add_argument("--market-packet", required=True)
    parser.add_argument("--observation", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    market = json.loads(Path(args.market_packet).read_text(encoding="utf-8"))
    observation = json.loads(Path(args.observation).read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas" / "visual_observation.schema.json").read_text(encoding="utf-8"))
    errors = [f"{error.json_path}: {error.message}" for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(observation)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    if observation["symbol"] != market["symbol"]:
        print("Observation symbol does not match market packet.", file=sys.stderr)
        return 2
    report = compare_visual_observation(market, observation)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"overall_status": report["overall_status"], "mode": report["mode"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
