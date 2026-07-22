from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from ctl_analysis_registry.acceptance import run_acceptance_audit, write_acceptance_artifacts
from ctl_analysis_registry.paths import DEFAULT_WORKSPACE_CONFIG, load_registry_paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the immutable Phase 2 Analysis Registry acceptance audit.")
    parser.add_argument("--registry-config", type=Path, default=DEFAULT_WORKSPACE_CONFIG)
    parser.add_argument("--registry-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker-control", type=Path)
    args = parser.parse_args(argv)
    paths = load_registry_paths(args.registry_config, registry_root=args.registry_root)
    worker_control = args.worker_control or (paths.root / "worker-control.json")
    worker = None
    if worker_control.exists():
        worker = json.loads(worker_control.read_text(encoding="utf-8"))
    result = run_acceptance_audit(paths.ledger, paths.sqlite, worker, paths=paths)
    json_path, markdown_path = write_acceptance_artifacts(result, args.output)
    print(json.dumps({
        **paths.metadata(), "core_gate": result["core_gate"], "worker_gate": result["worker_gate"],
        "ledger_index_parity": result["ledger_index_parity"],
        "order_actions": result["order_actions"],
        "permission_leakage": result["permission_leakage"],
        "json": str(json_path), "markdown": str(markdown_path),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result["core_gate"] == "PHASE2_CORE_COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
