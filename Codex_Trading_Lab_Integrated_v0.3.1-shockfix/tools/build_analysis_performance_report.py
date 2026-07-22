from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ctl_analysis_registry.events import build_v2_event
from ctl_analysis_registry.identity import canonical_json, sha256_hex, stable_id
from ctl_analysis_registry.ledger import AppendOnlyLedger
from ctl_analysis_registry.reporting import build_coverage_report, build_performance_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build descriptive Analysis Registry performance reports.")
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--system", choices=["ZENITH", "CHAT_MODEL"])
    parser.add_argument("--horizon")
    parser.add_argument("--publish-ledger", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    cohort_filter = {key: value for key, value in {"system": args.system, "horizon": args.horizon}.items() if value}
    with sqlite3.connect(args.sqlite) as connection:
        coverage = build_coverage_report(connection, cohort_filter)
        performance = build_performance_report(connection, cohort_filter)
    report = {"coverage": coverage, "performance": performance}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.publish_ledger:
        report_hash = sha256_hex(canonical_json(report))
        ledger = AppendOnlyLedger(args.publish_ledger)
        events = ledger.read_all()
        event_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        event = build_v2_event(
            {
                "event_id": stable_id("EVENT", "REPORT_PUBLISHED", report_hash),
                "event_type": "REPORT_PUBLISHED", "event_time": event_time,
                "decision_time": None, "source_class": "SYNTHETIC", "integrity_tier": "VERIFIED",
                "producer": "tools.build_analysis_performance_report",
                "payload": {
                    "report_hash": report_hash, "cohort_filter": cohort_filter,
                    "policy_versions": ["DIRECTIONAL_TERMINAL_ATR_V1", "SINGLE_TARGET", "ORDERED_SCENARIO_V1"],
                    "generated_at": event_time, "evidence_refs": [str(args.output)],
                    "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0},
                },
            },
            previous_hash=events[-1]["event_hash"] if events else None,
        )
        ledger.append_fsynced(event)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
