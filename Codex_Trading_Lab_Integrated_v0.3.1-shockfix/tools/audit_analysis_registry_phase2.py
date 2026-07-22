from __future__ import annotations

import argparse
import json
from pathlib import Path

from ctl_analysis_registry.acceptance import run_acceptance_audit, write_acceptance_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the immutable Phase 2 Analysis Registry acceptance audit.")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker-control", type=Path)
    args = parser.parse_args()
    worker = None
    if args.worker_control is not None:
        worker = json.loads(args.worker_control.read_text(encoding="utf-8"))
    result = run_acceptance_audit(args.ledger, args.sqlite, worker)
    json_path, markdown_path = write_acceptance_artifacts(result, args.output)
    print(json.dumps({
        "core_gate": result["core_gate"], "worker_gate": result["worker_gate"],
        "ledger_index_parity": result["ledger_index_parity"],
        "order_actions": result["order_actions"],
        "permission_leakage": result["permission_leakage"],
        "json": str(json_path), "markdown": str(markdown_path),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result["core_gate"] == "PHASE2_CORE_COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
