from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ctl_analysis_registry.coordination import acquire_registry_writer
from ctl_analysis_registry.lease import LeaseBusyError
from ctl_analysis_registry.paths import resolve_registry_paths


NOW = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)


def test_sessions_contend_on_one_canonical_lease(tmp_path: Path) -> None:
    paths = resolve_registry_paths(tmp_path / "canonical")
    held = acquire_registry_writer(paths, "session-a", NOW)
    try:
        with pytest.raises(LeaseBusyError, match="session-a"):
            acquire_registry_writer(paths, "session-b", NOW)
        assert list(paths.root.parent.rglob("*.lease.json")) == [paths.lease]
    finally:
        held.release()


def test_operation_log_uses_canonical_path_during_stale_recovery(tmp_path: Path) -> None:
    paths = resolve_registry_paths(tmp_path / "canonical")
    old = acquire_registry_writer(paths, "old", NOW, ttl_seconds=1)
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
    assert old.path == paths.lease
