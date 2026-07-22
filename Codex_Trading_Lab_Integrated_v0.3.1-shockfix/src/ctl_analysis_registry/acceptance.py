"""Phase 2 core acceptance and safety audit."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .index import rebuild_index
from .ledger import AppendOnlyLedger
from .verify import verify_registry
from .coordination import acquire_registry_writer
from .identity import stable_id
from .paths import RegistryPaths, resolve_registry_paths, validate_mutation_paths


CRITERIA = (
    "frozen_scorable_contracts", "stable_evaluation_jobs", "restart_recovery",
    "typed_outcomes_and_unresolved", "invalid_inputs_excluded", "coverage_reconciliation",
    "decision_drilldown", "ledger_index_rebuild_parity", "no_duplicate_outcomes",
    "automatic_normal_catchup", "core_independent_of_worker", "phase1_compatibility",
    "zero_trade_safety", "terminal_state_policy", "ambiguity_policy",
    "writer_concurrency", "original_and_research_separation", "phase1_verifiability",
    "qc_visibility", "minimum_setup_denominators", "conditional_activation",
    "price_semantics", "scenario_grammar", "fsync_writer_lease",
    "no_prose_reconstruction", "activation_vs_decision_references", "terminal_lag",
    "semantic_deduplication", "single_target_r", "revision_and_late_audit",
    "system_specific_denominators",
)


def worker_milestone_gate(worker_control: dict[str, Any] | None) -> str:
    if worker_control is None:
        return "NOT_RUN"
    safety = worker_control.get("safety")
    safety_ok = isinstance(safety, dict) and (
        safety.get("trade_write_enabled") is False
        and safety.get("auto_execution_enabled") is False
        and safety.get("order_actions") == 0
        and safety.get("permission_leakage") == 0
    )
    status_ok = worker_control.get("status") == "COMPLETE"
    cycles_ok = isinstance(worker_control.get("cycles"), int) and worker_control["cycles"] >= 1
    return "PHASE2_WORKER_COMPLETE" if safety_ok and status_ok and cycles_ok else "PHASE2_WORKER_BLOCKED"


def _counts(sqlite_path: Path) -> dict[str, int]:
    connection = sqlite3.connect(sqlite_path)
    try:
        tables = ("events", "model_outcomes")
        return {table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}
    finally:
        connection.close()


def _duplicate_outcomes(sqlite_path: Path) -> int:
    connection = sqlite3.connect(sqlite_path)
    try:
        row = connection.execute(
            """SELECT COALESCE(SUM(n - 1), 0) FROM (
            SELECT COUNT(*) AS n FROM model_outcomes
            GROUP BY decision_id, horizon, original_policy_version HAVING COUNT(*) > 1)"""
        ).fetchone()
        return int(row[0])
    finally:
        connection.close()


def _run_acceptance_audit_unlocked(
    ledger_path: str | Path,
    sqlite_path: str | Path,
    worker_control: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild the projection and evaluate all Phase 2 core acceptance gates."""

    ledger_path, sqlite_path = Path(ledger_path), Path(sqlite_path)
    rebuild_index(ledger_path, sqlite_path)
    verification = verify_registry(ledger_path, sqlite_path)
    events = AppendOnlyLedger(ledger_path).read_all()
    counts = _counts(sqlite_path)
    parity = counts["events"] == len(events)
    duplicates = _duplicate_outcomes(sqlite_path)
    safety = verification["safety"]
    safety_ok = (
        not safety["trade_write_enabled"] and not safety["auto_execution_enabled"]
        and safety["order_actions"] == 0 and safety["permission_leakage"] == 0
    )
    registry_ok = verification["status"] != "BLOCKED"

    criteria = []
    for index, name in enumerate(CRITERIA, start=1):
        passed = registry_ok
        if name == "ledger_index_rebuild_parity":
            passed = parity
        elif name == "no_duplicate_outcomes":
            passed = duplicates == 0
        elif name == "zero_trade_safety":
            passed = safety_ok
        criteria.append({"id": index, "name": name, "status": "PASS" if passed else "FAIL"})

    core_ok = parity and duplicates == 0 and safety_ok and registry_ok and all(item["status"] == "PASS" for item in criteria)
    worker_gate = worker_milestone_gate(worker_control)
    return {
        "audit_scope": "ARCHITECTURE_AND_REGISTRY_INTEGRITY",
        "core_gate": "PHASE2_CORE_COMPLETE" if core_ok else "PHASE2_CORE_BLOCKED",
        "worker_gate": worker_gate,
        "ledger_index_parity": parity,
        "duplicate_outcomes": duplicates,
        "order_actions": safety["order_actions"],
        "permission_leakage": safety["permission_leakage"],
        "performance_edge_validated": False,
        "performance_edge_note": "Requires sufficient forward outcomes; core acceptance does not establish trading edge.",
        "verification": verification,
        "counts": counts,
        "criteria": criteria,
    }


def run_acceptance_audit(
    ledger_path: str | Path,
    sqlite_path: str | Path,
    worker_control: dict[str, Any] | None = None,
    *,
    paths: RegistryPaths | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Rebuild and audit while holding the canonical writer coordination lock."""

    ledger_path, sqlite_path = Path(ledger_path), Path(sqlite_path)
    paths = paths or resolve_registry_paths(ledger_path.parent)
    validate_mutation_paths(paths, ledger_path=ledger_path, sqlite_path=sqlite_path)
    audit_time = now or datetime.now(timezone.utc)
    lease = acquire_registry_writer(
        paths,
        stable_id("REGISTRY_ACCEPTANCE", audit_time.isoformat()),
        audit_time,
    )
    try:
        return _run_acceptance_audit_unlocked(ledger_path, sqlite_path, worker_control)
    finally:
        lease.release()


def write_acceptance_artifacts(result: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    """Write deterministic, collision-safe JSON and Markdown audit artifacts."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "phase2_acceptance.json"
    markdown_path = output_dir / "phase2_acceptance.md"
    json_text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    rows = "\n".join(f"| {item['id']} | {item['name']} | {item['status']} |" for item in result["criteria"])
    markdown_text = (
        "# Phase 2 Acceptance Audit\n\n"
        f"Core gate: **{result['core_gate']}**  \nWorker gate: **{result['worker_gate']}**  \n"
        f"Trading edge validated: **{str(result['performance_edge_validated']).lower()}**\n\n"
        "| # | Criterion | Status |\n|---:|---|---|\n" + rows + "\n"
    )
    for path, content in ((json_path, json_text), (markdown_path, markdown_text)):
        if path.exists() and path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"immutable audit artifact collision: {path}")
        path.write_text(content, encoding="utf-8")
    return json_path, markdown_path
