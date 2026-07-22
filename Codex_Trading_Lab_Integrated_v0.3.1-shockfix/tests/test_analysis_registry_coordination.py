from __future__ import annotations

from datetime import datetime, timezone
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ctl_analysis_registry.coordination import acquire_registry_writer
from ctl_analysis_registry.lease import LeaseBusyError
from ctl_analysis_registry.paths import resolve_registry_paths
from ctl_analysis_registry.paths import RegistryPathError
import ctl_analysis_registry.integration as integration
import ctl_analysis_registry.lease as lease_module


NOW = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)


def test_sessions_contend_on_one_canonical_lease(tmp_path: Path) -> None:
    paths = resolve_registry_paths(tmp_path / "canonical")
    held = acquire_registry_writer(paths, "session-a", NOW)
    try:
        with pytest.raises(LeaseBusyError, match="OS lock"):
            acquire_registry_writer(paths, "session-b", NOW)
        assert list(paths.root.parent.rglob("*.lease.json")) == [paths.lease]
    finally:
        held.release()


def test_operation_log_uses_canonical_path_during_stale_recovery(tmp_path: Path) -> None:
    paths = resolve_registry_paths(tmp_path / "canonical")
    paths.root.mkdir(parents=True)
    paths.lease.write_text(
        json.dumps(
            {
                "owner_id": "old",
                "acquired_at": NOW.isoformat(),
                "heartbeat_at": NOW.isoformat(),
                "ttl_seconds": 1,
            }
        ),
        encoding="utf-8",
    )
    recovered = acquire_registry_writer(
        paths,
        "new",
        datetime(2026, 7, 22, 9, 0, 2, tzinfo=timezone.utc),
    )
    try:
        assert paths.operations.exists()
        assert "STALE_REGISTRY_LEASE_RECOVERED" in paths.operations.read_text(encoding="utf-8")
    finally:
        recovered.release()


def test_active_os_lock_cannot_be_stolen_when_descriptor_looks_stale(tmp_path: Path) -> None:
    paths = resolve_registry_paths(tmp_path / "canonical")
    held = acquire_registry_writer(paths, "active", NOW, ttl_seconds=1)
    descriptor = json.loads(paths.lease.read_text(encoding="utf-8"))
    descriptor["heartbeat_at"] = "2020-01-01T00:00:00+00:00"
    paths.lease.write_text(json.dumps(descriptor), encoding="utf-8")
    try:
        with pytest.raises(LeaseBusyError):
            acquire_registry_writer(
                paths,
                "contender",
                datetime(2026, 7, 22, 9, 5, tzinfo=timezone.utc),
            )
    finally:
        held.release()


def test_integration_rejects_paths_that_do_not_match_mutation_targets(tmp_path: Path) -> None:
    paths = resolve_registry_paths(tmp_path / "canonical")
    with pytest.raises(RegistryPathError, match="does not match RegistryPaths"):
        integration.register_current_analysis(
            decision_state={},
            snapshot={},
            analysis_id="A1",
            ledger_path=tmp_path / "other" / "events.jsonl",
            sqlite_path=paths.sqlite,
            now=NOW,
            paths=paths,
        )
    assert not paths.lease.exists()


def test_descriptor_write_failure_does_not_poison_future_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = resolve_registry_paths(tmp_path / "canonical")
    original = lease_module._write_descriptor

    def fail(descriptor, payload):
        raise OSError("disk full")

    monkeypatch.setattr(lease_module, "_write_descriptor", fail)
    with pytest.raises(OSError, match="disk full"):
        acquire_registry_writer(paths, "failed", NOW)
    assert not paths.lease.exists()

    monkeypatch.setattr(lease_module, "_write_descriptor", original)
    acquired = acquire_registry_writer(paths, "next", NOW)
    acquired.release()


def test_writer_os_lock_blocks_a_separate_process(tmp_path: Path) -> None:
    paths = resolve_registry_paths(tmp_path / "canonical")
    code = """
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'src'))
from ctl_analysis_registry.coordination import acquire_registry_writer
from ctl_analysis_registry.paths import resolve_registry_paths
paths = resolve_registry_paths(Path(sys.argv[1]))
lease = acquire_registry_writer(paths, 'child', datetime.now(timezone.utc))
print('READY', flush=True)
sys.stdin.readline()
lease.release()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(paths.root)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "READY"
        with pytest.raises(LeaseBusyError, match="OS lock"):
            acquire_registry_writer(paths, "parent", datetime.now(timezone.utc))
    finally:
        if child.stdin is not None and child.poll() is None:
            child.stdin.write("stop\n")
            child.stdin.flush()
        child.wait(timeout=10)
    assert child.returncode == 0, child.stderr.read() if child.stderr is not None else ""
