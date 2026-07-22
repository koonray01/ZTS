from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctl_analysis_registry.paths import (
    CONFIG_SCHEMA_VERSION,
    PRODUCER_VERSION,
    RegistryPathError,
    load_registry_paths,
    resolve_registry_paths,
)


def test_cwd_does_not_change_canonical_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    canonical = tmp_path / "runtime" / "analysis_registry"
    first = resolve_registry_paths(canonical)
    other = tmp_path / "worktree" / "nested"
    other.mkdir(parents=True)
    monkeypatch.chdir(other)
    second = resolve_registry_paths(canonical)

    assert first == second
    assert first.root == canonical.resolve()
    assert first.ledger == canonical.resolve() / "events.jsonl"
    assert first.sqlite == canonical.resolve() / "index.sqlite"
    assert first.evidence == canonical.resolve() / "evidence"
    assert first.lease == canonical.resolve() / "writer.lease.json"
    assert first.operations == canonical.resolve() / "operations.jsonl"
    assert first.mode == "CANONICAL"


def test_registry_root_override_is_complete_and_labeled(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    alternate = tmp_path / "migration"

    paths = resolve_registry_paths(canonical, registry_root=alternate)

    assert paths.root == alternate.resolve()
    assert paths.ledger.parent == paths.root
    assert paths.sqlite.parent == paths.root
    assert paths.evidence.parent == paths.root
    assert paths.mode == "NON_CANONICAL"


def test_partial_mutation_override_fails_without_creating_root(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"

    with pytest.raises(RegistryPathError, match="partial mutation-path override"):
        resolve_registry_paths(
            canonical,
            mutation_overrides={"ledger": tmp_path / "events.jsonl"},
        )

    assert not canonical.exists()


def test_config_loader_is_strict_and_side_effect_free(tmp_path: Path) -> None:
    canonical = tmp_path / "runtime" / "analysis_registry"
    implementation = tmp_path / "implementation"
    config = tmp_path / "registry.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": CONFIG_SCHEMA_VERSION,
                "canonical_root": str(canonical),
                "implementation_root": str(implementation),
                "producer_version": PRODUCER_VERSION,
            }
        ),
        encoding="utf-8",
    )

    paths = load_registry_paths(config)

    assert paths.root == canonical.resolve()
    assert paths.config == config.resolve()
    assert not canonical.exists()


@pytest.mark.parametrize("field", ["schema_version", "canonical_root", "implementation_root", "producer_version"])
def test_config_loader_rejects_missing_required_field(tmp_path: Path, field: str) -> None:
    payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "canonical_root": str(tmp_path / "canonical"),
        "implementation_root": str(tmp_path / "implementation"),
        "producer_version": PRODUCER_VERSION,
    }
    payload.pop(field)
    config = tmp_path / "registry.json"
    config.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RegistryPathError, match="configuration keys"):
        load_registry_paths(config)


def test_config_loader_rejects_relative_paths_and_unknown_versions(tmp_path: Path) -> None:
    config = tmp_path / "registry.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": "UNKNOWN",
                "canonical_root": "relative/registry",
                "implementation_root": "relative/implementation",
                "producer_version": "UNKNOWN",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RegistryPathError):
        load_registry_paths(config)
