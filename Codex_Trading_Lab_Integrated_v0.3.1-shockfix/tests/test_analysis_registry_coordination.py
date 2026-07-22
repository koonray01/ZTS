from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from ctl_analysis_registry.coordination import acquire_registry_writer
from ctl_analysis_registry.lease import LeaseBusyError
from ctl_analysis_registry.paths import resolve_registry_paths
from ctl_analysis_registry.paths import RegistryPathError
import ctl_analysis_registry.integration as integration


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
