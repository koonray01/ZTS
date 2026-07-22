"""Canonical, side-effect-free path resolution for the Analysis Registry."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Mapping


CONFIG_SCHEMA_VERSION = "ANALYSIS_REGISTRY_CONFIG_V0_1"
PRODUCER_VERSION = "CTL_ANALYSIS_REGISTRY_V0_2"
DEFAULT_WORKSPACE_CONFIG = Path(
    r"D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry\registry.json"
)
_CONFIG_KEYS = {"schema_version", "canonical_root", "implementation_root", "producer_version"}
_MUTATION_KEYS = {"ledger", "sqlite", "evidence", "lease", "operations"}


class RegistryPathError(ValueError):
    """Raised before side effects when Registry path configuration is unsafe."""


@dataclass(frozen=True)
class RegistryPaths:
    root: Path
    ledger: Path
    sqlite: Path
    evidence: Path
    config: Path
    lease: Path
    operations: Path
    mode: Literal["CANONICAL", "NON_CANONICAL"]
    config_schema_version: str = CONFIG_SCHEMA_VERSION
    producer_version: str = PRODUCER_VERSION

    def metadata(self) -> dict[str, str]:
        return {
            "registry_root": str(self.root),
            "registry_mode": self.mode,
            "registry_config_schema_version": self.config_schema_version,
            "registry_producer_version": self.producer_version,
        }


def _absolute(path: str | Path, field: str) -> Path:
    value = Path(path)
    if not value.is_absolute():
        raise RegistryPathError(f"{field} must be an absolute path")
    return value.resolve()


def resolve_registry_paths(
    canonical_root: str | Path,
    registry_root: str | Path | None = None,
    mutation_overrides: Mapping[str, str | Path | None] | None = None,
) -> RegistryPaths:
    canonical = _absolute(canonical_root, "canonical_root")
    selected = _absolute(registry_root, "registry_root") if registry_root is not None else canonical
    supplied = {key: _absolute(value, key) for key, value in (mutation_overrides or {}).items() if value is not None}
    if supplied and set(supplied) != _MUTATION_KEYS:
        raise RegistryPathError("partial mutation-path override")
    values = supplied or {
        "ledger": selected / "events.jsonl",
        "sqlite": selected / "index.sqlite",
        "evidence": selected / "evidence",
        "lease": selected / "writer.lease.json",
        "operations": selected / "operations.jsonl",
    }
    return RegistryPaths(
        root=selected,
        ledger=values["ledger"],
        sqlite=values["sqlite"],
        evidence=values["evidence"],
        config=selected / "registry.json",
        lease=values["lease"],
        operations=values["operations"],
        mode="CANONICAL" if selected == canonical else "NON_CANONICAL",
    )


def load_registry_paths(
    config_path: str | Path = DEFAULT_WORKSPACE_CONFIG,
    registry_root: str | Path | None = None,
) -> RegistryPaths:
    config = _absolute(config_path, "config_path")
    try:
        payload = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryPathError(f"cannot load Registry configuration: {config}") from exc
    if not isinstance(payload, dict) or set(payload) != _CONFIG_KEYS:
        raise RegistryPathError(f"Registry configuration keys must be exactly {sorted(_CONFIG_KEYS)}")
    if payload["schema_version"] != CONFIG_SCHEMA_VERSION:
        raise RegistryPathError(f"unsupported Registry configuration schema: {payload['schema_version']}")
    if payload["producer_version"] != PRODUCER_VERSION:
        raise RegistryPathError(f"unsupported Registry producer: {payload['producer_version']}")
    _absolute(payload["implementation_root"], "implementation_root")
    paths = resolve_registry_paths(payload["canonical_root"], registry_root=registry_root)
    return replace(paths, config=config)


def validate_mutation_paths(
    paths: RegistryPaths,
    *,
    ledger_path: str | Path,
    sqlite_path: str | Path | None = None,
    evidence_root: str | Path | None = None,
) -> None:
    comparisons = {"ledger": (_absolute(ledger_path, "ledger_path"), paths.ledger)}
    if sqlite_path is not None:
        comparisons["sqlite"] = (_absolute(sqlite_path, "sqlite_path"), paths.sqlite)
    if evidence_root is not None:
        comparisons["evidence"] = (_absolute(evidence_root, "evidence_root"), paths.evidence)
    mismatches = [name for name, (actual, expected) in comparisons.items() if actual != expected]
    if mismatches:
        raise RegistryPathError(f"mutation target does not match RegistryPaths: {', '.join(mismatches)}")
