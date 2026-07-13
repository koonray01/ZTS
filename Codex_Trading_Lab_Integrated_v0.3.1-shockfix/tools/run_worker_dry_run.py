from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_decision_core import run_decision_core  # noqa: E402
from ctl_permission_agent.jobs import build_codex_job  # noqa: E402
from ctl_codex_worker import (  # noqa: E402
    CodexWorker,
    ResultStore,
    ScriptedProvider,
    StateRegistry,
    WorkerJobStore,
)
from ctl_codex_worker.audit import verify_journal  # noqa: E402
from ctl_codex_worker.job_store import verify_job_store  # noqa: E402
from ctl_codex_worker.result_store import verify_result_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a scripted Codex worker dry run.")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    now = datetime(2025, 3, 6, 0, 0, tzinfo=timezone.utc)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    decision = run_decision_core(snapshot)
    state = {**decision, "snapshot": snapshot}

    registry = StateRegistry(output / "state_registry.json")
    registry.put(snapshot["snapshot_id"], state)

    job = build_codex_job(
        snapshot_id=snapshot["snapshot_id"],
        event_types=["MARKET_STATE_CHANGED"],
        input_refs=[
            decision["market_packet"]["market_packet_id"],
            decision["scenario_packet"]["scenario_packet_id"],
        ],
        now=now,
    )

    job_store = WorkerJobStore(output / "worker_jobs.jsonl")
    result_store = ResultStore(output / "worker_results.jsonl")
    job_store.enqueue(job, now=now)

    script = json.loads(
        (ROOT / "examples" / "provider_scripts" / "market_read.json").read_text(
            encoding="utf-8"
        )
    )
    # Replace the demonstration evidence reference with a real packet ID.
    script[1]["final"]["facts"][0]["evidence_refs"] = [
        decision["market_packet"]["market_packet_id"]
    ]

    worker = CodexWorker(
        worker_id="WORKER-DEMO-001",
        job_store=job_store,
        result_store=result_store,
        state_registry=registry,
        skills_root=ROOT / "skills",
        schemas_root=ROOT / "schemas",
        audit_path=output / "worker_audit.jsonl",
        provider_factory=lambda _job: ScriptedProvider(
            turns=json.loads(json.dumps(script))
        ),
    )
    report = worker.run_once(now=now)

    summary = {
        "job_id": job["job_id"],
        "worker_status": report["status"],
        "result_id": None if report.get("result") is None else report["result"]["result_id"],
        "permission_claim": None if report.get("result") is None else report["result"]["permission_claim"],
        "effective_tools": report.get("effective_tools", []),
        "job_store_integrity": verify_job_store(job_store.path)[0],
        "result_store_integrity": verify_result_store(result_store.path)[0],
        "audit_integrity": verify_journal(output / "worker_audit.jsonl")[0],
        "live_provider_connected": False,
        "auto_execution_enabled": False,
        "output": str(output),
    }
    (output / "worker_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary))
    return 0 if report["status"] == "SUCCEEDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
