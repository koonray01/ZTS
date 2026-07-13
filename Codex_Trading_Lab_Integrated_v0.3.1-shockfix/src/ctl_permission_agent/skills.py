from __future__ import annotations

from typing import Any

SKILL_REGISTRY = {
    "ctl-market-read": {
        "version": "0.1.0",
        "allowed_tools": ["get_current_state", "inspect_evidence_refs"],
    },
    "ctl-scenario-planner": {
        "version": "0.1.0",
        "allowed_tools": ["get_current_state", "inspect_evidence_refs"],
    },
    "ctl-entry-evaluator": {
        "version": "0.1.0",
        "allowed_tools": ["list_entry_candidates", "inspect_evidence_refs"],
    },
    "ctl-part3-preexecute": {
        "version": "0.1.0",
        "allowed_tools": ["list_entry_candidates", "run_part3", "explain_decision"],
    },
    "ctl-evidence-audit": {
        "version": "0.1.0",
        "allowed_tools": ["inspect_evidence_refs", "get_current_state"],
    },
    "ctl-live-event-review": {
        "version": "0.1.0",
        "allowed_tools": ["get_current_state", "list_entry_candidates", "build_codex_job"],
    },
}


def validate_skill(skill_id: str, version: str, requested_tools: list[str]) -> tuple[bool, list[str]]:
    errors = []
    skill = SKILL_REGISTRY.get(skill_id)
    if skill is None:
        return False, [f"Unknown skill: {skill_id}"]
    if skill["version"] != version:
        errors.append(f"Skill version mismatch: expected {skill['version']}, got {version}")
    disallowed = sorted(set(requested_tools) - set(skill["allowed_tools"]))
    if disallowed:
        errors.append("Disallowed tools: " + ", ".join(disallowed))
    return not errors, errors
