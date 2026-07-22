from __future__ import annotations

from pathlib import Path

from ctl_analysis_registry.acceptance import run_acceptance_audit
from ctl_analysis_registry.acceptance import write_acceptance_artifacts
from ctl_analysis_registry.index import rebuild_index
from ctl_analysis_registry.coordination import acquire_registry_writer
from ctl_analysis_registry.lease import LeaseBusyError
from ctl_analysis_registry.paths import resolve_registry_paths
from datetime import datetime, timezone
import pytest


def test_phase2_core_acceptance_reconciles_and_has_zero_safety_leakage(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    ledger.write_text("", encoding="utf-8")
    sqlite = tmp_path / "index.sqlite"
    rebuild_index(ledger, sqlite)

    result = run_acceptance_audit(ledger, sqlite)

    assert result["core_gate"] == "PHASE2_CORE_COMPLETE"
    assert result["ledger_index_parity"] is True
    assert result["duplicate_outcomes"] == 0
    assert result["order_actions"] == 0
    assert result["permission_leakage"] == 0
    assert len(result["criteria"]) == 31


def test_worker_not_run_does_not_block_core(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    ledger.write_text("", encoding="utf-8")
    sqlite = tmp_path / "index.sqlite"
    rebuild_index(ledger, sqlite)
    result = run_acceptance_audit(ledger, sqlite)
    assert result["worker_gate"] == "NOT_RUN"
    assert result["core_gate"] == "PHASE2_CORE_COMPLETE"


def test_acceptance_artifacts_are_idempotent_and_reject_collisions(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    ledger.write_text("", encoding="utf-8")
    result = run_acceptance_audit(ledger, tmp_path / "index.sqlite")
    first = write_acceptance_artifacts(result, tmp_path / "audit")
    second = write_acceptance_artifacts(result, tmp_path / "audit")
    assert first == second
    changed = {**result, "core_gate": "PHASE2_CORE_BLOCKED"}
    try:
        write_acceptance_artifacts(changed, tmp_path / "audit")
    except FileExistsError:
        pass
    else:
        raise AssertionError("changed immutable audit should collide")


def test_acceptance_index_rebuild_contends_on_canonical_writer_lease(tmp_path: Path) -> None:
    paths = resolve_registry_paths(tmp_path / "registry")
    paths.root.mkdir(parents=True)
    paths.ledger.write_text("", encoding="utf-8")
    now = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)
    held = acquire_registry_writer(paths, "other", now)
    try:
        with pytest.raises(LeaseBusyError):
            run_acceptance_audit(paths.ledger, paths.sqlite, paths=paths, now=now)
    finally:
        held.release()
