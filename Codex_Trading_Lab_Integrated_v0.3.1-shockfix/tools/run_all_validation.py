from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(name: str, args: list[str], output_root: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "name": name,
        "command": [sys.executable, *args],
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all integrated fixture validations.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    snapshot = ROOT / "examples" / "snapshots" / "directional_market.snapshot.json"
    results = []
    results.append(run("pytest", ["-m", "pytest", "-q"], output))
    results.append(run("basic_eyes", [str(ROOT / "tools" / "run_eyes.py"), "--snapshot", str(snapshot), "--output", str(output / "basic_eyes.json")], output))
    results.append(run("advanced_eyes", [str(ROOT / "tools" / "run_advanced_eyes.py"), "--snapshot", str(snapshot), "--output", str(output / "advanced_eyes.json")], output))
    results.append(run("decision_core", [str(ROOT / "tools" / "run_decision_core.py"), "--snapshot", str(snapshot), "--output", str(output / "decision_core")], output))
    results.append(run("permission_agent", [str(ROOT / "tools" / "run_permission_agent.py"), "--snapshot", str(snapshot), "--output", str(output / "permission_agent")], output))
    results.append(run("live_runtime", [str(ROOT / "tools" / "run_live_session.py"), "--snapshots", str(ROOT / "examples" / "live_sequence"), "--output", str(output / "live_runtime")], output))
    results.append(run("replay", [str(ROOT / "tools" / "run_replay_case.py"), "--case", str(ROOT / "examples" / "cases" / "bullish_continuation"), "--decision", str(ROOT / "examples" / "decisions" / "bullish_continuation.correct.json"), "--output", str(output / "replay")], output))
    results.append(run("learning", [str(ROOT / "tools" / "run_learning_cycle.py"), "--cases-root", str(ROOT / "examples" / "cases"), "--decisions-root", str(ROOT / "examples" / "decisions"), "--output", str(output / "learning")], output))
    results.append(run("worker", [str(ROOT / "tools" / "run_worker_dry_run.py"), "--snapshot", str(snapshot), "--output", str(output / "worker")], output))

    summary = {
        "all_passed": all(item["exit_code"] == 0 for item in results),
        "results": results,
        "real_mt5_connected": False,
        "live_model_provider_connected": False,
        "auto_execution_enabled": False,
    }
    (output / "validation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "all_passed": summary["all_passed"],
        "checks": len(results),
        "failed": [item["name"] for item in results if item["exit_code"] != 0],
        "output": str(output),
    }))
    return 0 if summary["all_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
