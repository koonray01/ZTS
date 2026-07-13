from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_visual_parity import summarize_visual_parity_reports  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize metadata-bound Visual Parity QA reports.")
    parser.add_argument("--reports", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    reports = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.reports]
    summary = summarize_visual_parity_reports(reports)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"calibration_status": summary["calibration_status"], "observation_count": summary["observation_count"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
