from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ctl_replay_training.case import ReplayCase
from ctl_replay_training.visibility import enforce_visible_snapshot
from render_market_chart import render


def main() -> int:
    parser = argparse.ArgumentParser(description="Render one cutoff-safe replay stage.")
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--step", required=True)
    parser.add_argument("--decision-state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bars", type=int, default=30)
    parser.add_argument("--mode", choices=["blind", "audit", "outcome"], default="audit")
    parser.add_argument("--outcome", type=Path)
    args = parser.parse_args()
    case = ReplayCase.load(args.case)
    if args.mode == "outcome" and args.outcome is None:
        parser.error("--outcome is required in outcome mode")
    if args.mode == "outcome" and args.step != case.steps[-1]["step_id"]:
        parser.error("outcome mode is only available at the final replay step")
    step = next(item for item in case.steps if item["step_id"] == args.step)
    visible = enforce_visible_snapshot(case.load_snapshot(step), step["replay_time"])
    temp = args.output.parent / f".{args.output.stem}.cutoff.snapshot.json"
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_text(json.dumps(visible), encoding="utf-8")
    decision_path = args.decision_state
    blank = None
    if args.mode == "blind":
        blank = args.output.parent / f".{args.output.stem}.blind.decision.json"
        blank.write_text("{}", encoding="utf-8")
        decision_path = blank
    try:
        result = render(temp, decision_path, args.output, args.bars)
    finally:
        temp.unlink(missing_ok=True)
        if blank is not None:
            blank.unlink(missing_ok=True)
    report = {"step_id": args.step, "replay_time": step["replay_time"], "mode": args.mode, "cutoff_safe": True, "render": result}
    if args.mode == "outcome":
        report["outcome"] = json.loads(args.outcome.read_text(encoding="utf-8"))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        (args.output.parent / "outcome_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
