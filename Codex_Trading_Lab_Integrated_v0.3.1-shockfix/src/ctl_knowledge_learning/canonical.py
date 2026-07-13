from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import atomic_write_json, iso_z, load_json, sha256_json, utc_now


class PolicyAlreadyExists(RuntimeError):
    pass


class HumanApprovalRequired(PermissionError):
    pass


class CanonicalPolicyStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.state = load_json(
            self.path,
            default={"policies": {}, "deprecations": {}},
        )
        self.state.setdefault("policies", {})
        self.state.setdefault("deprecations", {})

    def _persist(self) -> None:
        atomic_write_json(self.path, self.state)

    def create_version(
        self,
        *,
        policy_id: str,
        version: str,
        content: dict[str, Any],
        source_refs: list[str],
        dependencies: dict[str, str],
        human_approved: bool,
        approved_at: datetime | None = None,
    ) -> dict[str, Any]:
        if not human_approved:
            raise HumanApprovalRequired(
                "Canonical policy requires explicit human approval."
            )
        key = f"{policy_id}@{version}"
        if key in self.state["policies"]:
            raise PolicyAlreadyExists(f"Policy version already exists: {key}")

        body = {
            "schema_version": "0.1.0",
            "policy_id": policy_id,
            "version": version,
            "status": "LOCKED",
            "content": content,
            "approved_by_human": True,
            "approved_at": iso_z(approved_at or utc_now()),
            "source_refs": list(dict.fromkeys(source_refs)),
            "dependencies": dependencies,
        }
        policy = {**body, "policy_hash": sha256_json(body)}
        self.state["policies"][key] = policy
        self._persist()
        return dict(policy)

    def deprecate(
        self,
        policy_id: str,
        version: str,
        *,
        human_approved: bool,
        deprecated_at: datetime | None = None,
    ) -> dict[str, Any]:
        if not human_approved:
            raise HumanApprovalRequired("Deprecation requires human approval.")
        key = f"{policy_id}@{version}"
        original = self.state["policies"][key]
        self.state["deprecations"][key] = {
            "deprecated_at": iso_z(deprecated_at or utc_now()),
            "approved_by_human": True,
            "original_policy_hash": original["policy_hash"],
        }
        self._persist()
        return self.get(policy_id, version)

    def get(self, policy_id: str, version: str) -> dict[str, Any]:
        key = f"{policy_id}@{version}"
        original = dict(self.state["policies"][key])
        if key not in self.state["deprecations"]:
            return original
        deprecated_body = {
            key_name: value
            for key_name, value in original.items()
            if key_name != "policy_hash"
        }
        deprecated_body["status"] = "DEPRECATED"
        return {
            **deprecated_body,
            "policy_hash": sha256_json(deprecated_body),
        }

    def list(self) -> list[dict[str, Any]]:
        return [
            self.get(
                policy["policy_id"],
                policy["version"],
            )
            for policy in self.state["policies"].values()
        ]
