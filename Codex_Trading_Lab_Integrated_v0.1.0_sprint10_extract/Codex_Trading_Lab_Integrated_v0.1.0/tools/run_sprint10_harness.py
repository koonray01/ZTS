from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_mt5_snapshot import FixtureSnapshotAdapter, MetaTrader5SnapshotAdapter, SnapshotUnavailable, run_integration_harness  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Sprint 10 integration harness.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--real-mt5", action="store_true")
    args = parser.parse_args()
    adapter = MetaTrader5SnapshotAdapter() if args.real_mt5 else FixtureSnapshotAdapter()
    report = run_integration_harness(output_root=args.output, symbol=args.symbol, adapter=adapter, iterations=args.iterations)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "harness_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"final_decision": report["final_decision"], "source": report["source"], "snapshots_processed": report["snapshots_processed"], "integrity": report["integrity"], "trade_write_enabled": False}))
    return 0 if not report["integrity"]["errors"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SnapshotUnavailable as exc:
        print(json.dumps({"status": "REAL_MT5_UNAVAILABLE", "message": str(exc), "fallback_used": False}), file=sys.stderr)
        raise SystemExit(3)
