from __future__ import annotations

from datetime import datetime
from typing import Any

from .utils import iso_z, sanitize_id, utc_now


def build_change_proposal(
    *,
    proposal_type: str,
    target_id: str,
    from_version: str | None,
    to_version: str,
    rationale: str,
    evidence_refs: list[str],
    tests_required: list[str],
    shadow_plan: str,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "proposal_id": sanitize_id(
            f"PROPOSAL_{proposal_type}_{target_id}_{to_version}"
        ),
        "proposal_type": proposal_type,
        "target_id": target_id,
        "from_version": from_version,
        "to_version": to_version,
        "status": "DRAFT",
        "rationale": rationale,
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
        "tests_required": tests_required,
        "shadow_plan": shadow_plan,
        "human_approval_required": True,
        "human_approved": False,
        "created_at": iso_z(created_at or utc_now()),
    }


def build_skill_update_proposal(
    *,
    skill_id: str,
    current_version: str,
    proposed_version: str,
    approved_policy_refs: list[str],
    dependency_changes: dict[str, str],
    created_at: datetime | None = None,
) -> dict[str, Any]:
    proposal = build_change_proposal(
        proposal_type="SKILL_UPDATE",
        target_id=skill_id,
        from_version=current_version,
        to_version=proposed_version,
        rationale="Align skill instructions with approved canonical policy versions.",
        evidence_refs=approved_policy_refs,
        tests_required=[
            "skill_manifest_schema",
            "dependency_guard",
            "regression_suite",
            "shadow_job_replay",
        ],
        shadow_plan="Run skill in shadow mode without changing production outputs.",
        created_at=created_at,
    )
    proposal["dependency_changes"] = dependency_changes
    proposal["automatic_deployment_allowed"] = False
    return proposal
