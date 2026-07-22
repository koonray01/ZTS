from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_analysis_registry.coordination import acquire_registry_writer
from ctl_analysis_registry.events import build_v2_event
from ctl_analysis_registry.identity import canonical_json, sha256_hex, stable_id
from ctl_analysis_registry.index import rebuild_index
from ctl_analysis_registry.ledger import AppendOnlyLedger
from ctl_analysis_registry.paths import DEFAULT_WORKSPACE_CONFIG, RegistryPathError, load_registry_paths
from ctl_analysis_registry.reporting import build_coverage_report, build_performance_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build descriptive Analysis Registry performance reports.")
    parser.add_argument("--registry-config", type=Path, default=DEFAULT_WORKSPACE_CONFIG)
    parser.add_argument("--registry-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--system", choices=["ZENITH", "CHAT_MODEL"])
    parser.add_argument("--horizon")
    parser.add_argument("--publish-ledger", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = load_registry_paths(args.registry_config, registry_root=args.registry_root)
    cohort_filter = {key: value for key, value in {"system": args.system, "horizon": args.horizon}.items() if value}
    with sqlite3.connect(paths.sqlite) as connection:
        coverage = build_coverage_report(connection, cohort_filter)
        performance = build_performance_report(connection, cohort_filter)
    report = {"coverage": coverage, "performance": performance}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.publish_ledger:
        if args.publish_ledger.resolve() != paths.ledger:
            raise RegistryPathError("published report ledger must equal the resolved canonical ledger")
        report_hash = sha256_hex(canonical_json(report))
        event_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        lease = acquire_registry_writer(paths, stable_id("REPORT_PUBLISHER", report_hash), datetime.now(timezone.utc))
        try:
            ledger = AppendOnlyLedger(paths.ledger)
            events = ledger.read_all()
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
            rebuild_index(paths.ledger, paths.sqlite)
        finally:
            lease.release()
    print(json.dumps({**paths.metadata(), **report}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
