from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import tools.analysis_registry_status as status_cli
import tools.audit_analysis_registry_phase2 as audit_cli
import tools.build_analysis_performance_report as performance_cli
import tools.run_analysis_outcome_worker as worker_cli
from ctl_analysis_registry.acceptance import worker_milestone_gate
from ctl_analysis_registry.paths import CONFIG_SCHEMA_VERSION, PRODUCER_VERSION


@pytest.mark.parametrize(
    "tool",
    [
        "analysis_registry_status.py",
        "audit_analysis_registry_phase2.py",
        "build_analysis_performance_report.py",
        "run_analysis_outcome_worker.py",
        "record_analysis_registry.py",
        "rebuild_analysis_registry.py",
        "verify_analysis_registry.py",
        "catch_up_analysis_registry.py",
        "backfill_analysis_registry_phase2.py",
    ],
)
def test_phase2_operator_cli_bootstraps_src_without_pythonpath(tool: str) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(Path("tools") / tool), "--help"],
        text=True,
        capture_output=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CONFIG_SCHEMA_VERSION,
                "canonical_root": str(tmp_path / "canonical"),
                "implementation_root": str(tmp_path / "implementation"),
                "producer_version": PRODUCER_VERSION,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_status_cli_uses_canonical_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    config = _config(tmp_path)
    observed = {}

    def status(sqlite, now):
        observed["sqlite"] = sqlite
        return {"status": "PASS"}

    monkeypatch.setattr(status_cli, "registry_status", status)
    assert status_cli.main(["--registry-config", str(config)]) == 0
    response = json.loads(capsys.readouterr().out)
    assert observed["sqlite"] == (tmp_path / "canonical" / "index.sqlite").resolve()
    assert response["registry_mode"] == "CANONICAL"


def test_worker_cli_binds_all_runtime_paths_to_canonical_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    config = _config(tmp_path)
    observed = {}

    def run_worker(runtime, stop_file):
        observed.update(runtime)
        observed["stop_file"] = stop_file
        return {"status": "COMPLETE", "cycles": 1, "processed": 0, "resolved": 0, "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0}}

    monkeypatch.setattr(worker_cli, "MetaTrader5SnapshotAdapter", object)
    monkeypatch.setattr(worker_cli, "run_worker", run_worker)
    assert worker_cli.main(["--registry-config", str(config), "--interval-seconds", "0"]) == 0
    response = json.loads(capsys.readouterr().out)
    root = (tmp_path / "canonical").resolve()
    assert observed["ledger_path"] == root / "events.jsonl"
    assert observed["sqlite_path"] == root / "index.sqlite"
    assert observed["evidence_root"] == root / "evidence"
    assert observed["control_path"] == root / "worker-control.json"
    assert observed["stop_file"] == root / "worker.stop"
    assert response["worker_gate"] == "PHASE2_WORKER_COMPLETE"


def test_worker_milestone_requires_cycle_and_zero_trade_safety() -> None:
    complete = {
        "status": "COMPLETE",
        "cycles": 1,
        "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0},
    }
    assert worker_milestone_gate(complete) == "PHASE2_WORKER_COMPLETE"
    assert worker_milestone_gate({**complete, "cycles": 0}) == "PHASE2_WORKER_BLOCKED"
    assert worker_milestone_gate({**complete, "safety": {**complete["safety"], "order_actions": 1}}) == "PHASE2_WORKER_BLOCKED"


def test_audit_cli_uses_canonical_paths_and_worker_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    config = _config(tmp_path)
    root = (tmp_path / "canonical").resolve()
    root.mkdir(parents=True)
    (root / "worker-control.json").write_text(json.dumps({"status": "COMPLETE", "cycles": 1, "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0}}), encoding="utf-8")
    observed = {}

    def audit(ledger, sqlite, worker, **kwargs):
        observed.update({"ledger": ledger, "sqlite": sqlite, "worker": worker, **kwargs})
        return {"core_gate": "PHASE2_CORE_COMPLETE", "worker_gate": "PHASE2_WORKER_COMPLETE", "ledger_index_parity": True, "order_actions": 0, "permission_leakage": 0}

    monkeypatch.setattr(audit_cli, "run_acceptance_audit", audit)
    monkeypatch.setattr(audit_cli, "write_acceptance_artifacts", lambda result, output: (output / "phase2_acceptance.json", output / "phase2_acceptance.md"))
    assert audit_cli.main(["--registry-config", str(config), "--output", str(tmp_path / "audit")]) == 0
    capsys.readouterr()
    assert observed["ledger"] == root / "events.jsonl"
    assert observed["sqlite"] == root / "index.sqlite"
    assert observed["paths"].root == root
    assert observed["worker"]["status"] == "COMPLETE"


def test_performance_cli_defaults_to_canonical_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    config = _config(tmp_path)
    observed = {}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def connect(path):
        observed["sqlite"] = path
        return Connection()

    monkeypatch.setattr(performance_cli.sqlite3, "connect", connect)
    monkeypatch.setattr(performance_cli, "build_coverage_report", lambda connection, cohort: {"total_jobs": 0})
    monkeypatch.setattr(performance_cli, "build_performance_report", lambda connection, cohort: {"claims": {"validated_edge": False}})
    assert performance_cli.main(["--registry-config", str(config), "--output", str(tmp_path / "report.json")]) == 0
    response = json.loads(capsys.readouterr().out)
    assert observed["sqlite"] == (tmp_path / "canonical" / "index.sqlite").resolve()
    assert response["registry_mode"] == "CANONICAL"
    assert response["performance"]["claims"]["validated_edge"] is False
