from __future__ import annotations

from datetime import datetime, timezone

import ctl_analysis_registry.worker as worker


NOW = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)


def _config(tmp_path, cycles):
    return {
        "ledger_path": tmp_path / "events.jsonl", "sqlite_path": tmp_path / "index.sqlite",
        "evidence_root": tmp_path / "evidence", "adapter": object(),
        "cycles": cycles, "interval_seconds": 0, "max_jobs": 5, "now": NOW,
        "control_path": tmp_path / "worker-control.json",
    }


def test_worker_defers_when_analysis_command_holds_lease(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(worker, "run_catchup", lambda **kwargs: {"status": "DEFERRED", "processed": 0, "resolved": 0, "remaining": 1})

    result = worker.run_worker(_config(tmp_path, cycles=1), stop_file=tmp_path / "stop")

    assert result["status"] == "DEFERRED"
    assert result["processed"] == 0


def test_worker_restart_processes_persisted_due_jobs(monkeypatch, tmp_path) -> None:
    calls = []
    monkeypatch.setattr(worker, "run_catchup", lambda **kwargs: calls.append(1) or {"status": "COMPLETE", "processed": 1, "resolved": 1, "remaining": 0})

    first = worker.run_worker(_config(tmp_path, cycles=0), stop_file=tmp_path / "stop")
    second = worker.run_worker(_config(tmp_path, cycles=1), stop_file=tmp_path / "stop")

    assert first["processed"] == 0
    assert second["processed"] == 1
    assert len(calls) == 1


def test_worker_consumes_stop_file_without_catchup(monkeypatch, tmp_path) -> None:
    stop = tmp_path / "stop"
    stop.write_text("stop", encoding="utf-8")
    monkeypatch.setattr(worker, "run_catchup", lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not run")))

    result = worker.run_worker(_config(tmp_path, cycles=3), stop_file=stop)
    assert result["status"] == "STOPPED"
