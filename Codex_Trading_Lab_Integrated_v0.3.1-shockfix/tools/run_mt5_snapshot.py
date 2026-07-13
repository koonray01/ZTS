from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_mt5_snapshot import EvidenceStore, FixtureSnapshotAdapter, MetaTrader5SnapshotAdapter, SnapshotUnavailable  # noqa: E402
from ctl_mt5_snapshot.utils import sanitize_id  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a read-only Sprint 10 snapshot.")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--run-id", default="RUN-SPRINT10-SNAPSHOT")
    parser.add_argument("--bars", type=int, default=60)
    parser.add_argument("--output", required=True)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--no-h4", action="store_true")
    args = parser.parse_args()
    adapter = FixtureSnapshotAdapter() if args.fixture else MetaTrader5SnapshotAdapter()
    snapshot = adapter.capture(symbol=args.symbol, run_id=sanitize_id(args.run_id), bars=args.bars, include_h4=not args.no_h4)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "snapshot.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    evidence = EvidenceStore(output / "evidence")
    evidence_result = evidence.write_raw_snapshot(snapshot)
    print(json.dumps({"snapshot_id": snapshot["snapshot_id"], "source": snapshot["source"], "qc": snapshot["qc"]["decision"], "freshness": snapshot["freshness"]["status"], "evidence": evidence_result, "trade_write_enabled": False}))
    return 0 if snapshot["qc"]["decision"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SnapshotUnavailable as exc:
        print(json.dumps({"status": "REAL_MT5_UNAVAILABLE", "message": str(exc), "fallback_used": False, "trade_write_enabled": False}), file=sys.stderr)
        raise SystemExit(3)
