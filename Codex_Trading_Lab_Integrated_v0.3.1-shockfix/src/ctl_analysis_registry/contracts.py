"""Typed Phase 2 registry contracts and schema dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
V2_SCHEMA_VERSION = "ANALYSIS_REGISTRY_EVENT_V0_2"
PHASE2_EVENT_TYPES = {
    "DECISION_FROZEN",
    "EVALUATION_JOB_SCHEDULED",
    "DECISION_ACTIVATED",
    "FOLLOWUP_EVIDENCE_RECORDED",
    "MODEL_OUTCOME_RECORDED",
    "REPORT_PUBLISHED",
}
DECISION_TYPES = {"DIRECTIONAL", "SCENARIO", "SETUP", "ABSTENTION"}
SYSTEMS = {"ZENITH", "CHAT_MODEL"}

_PAYLOAD_SCHEMAS = {
    "DECISION_FROZEN": "frozen_model_decision.schema.json",
    "DECISION_ACTIVATED": "frozen_model_decision.schema.json",
    "EVALUATION_JOB_SCHEDULED": "evaluation_job.schema.json",
    "FOLLOWUP_EVIDENCE_RECORDED": "followup_evidence.schema.json",
    "MODEL_OUTCOME_RECORDED": "model_outcome.schema.json",
}


def _schema(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def schema_errors(schema_name: str, payload: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(_schema(schema_name), format_checker=FormatChecker())
    return sorted(
        f"{'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in validator.iter_errors(payload)
    )


def validate_phase2_payload(event_type: str, payload: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors for one typed Phase 2 payload."""

    if event_type not in PHASE2_EVENT_TYPES:
        return [f"unsupported Phase 2 event type: {event_type}"]
    schema_name = _PAYLOAD_SCHEMAS.get(event_type)
    if schema_name is None:
        return []
    errors = schema_errors(schema_name, payload)
    if event_type not in {"DECISION_FROZEN", "DECISION_ACTIVATED"}:
        return errors
    subtype = payload.get("decision_subtype")
    if subtype == "CONDITIONAL_DIRECTIONAL" and "activation" not in payload:
        errors.append("activation is required for CONDITIONAL_DIRECTIONAL")
    if subtype == "CONDITIONAL_SETUP":
        for field in (
            "activation",
            "setup_geometry",
            "strictness",
            "generation_id",
            "geometry_provenance",
        ):
            if field not in payload:
                errors.append(f"{field} is required for CONDITIONAL_SETUP")
    if subtype == "UNCONDITIONAL_DIRECTIONAL":
        if "reference_price" not in payload:
            errors.append("reference_price is required for UNCONDITIONAL_DIRECTIONAL")
        if "atr" not in payload:
            errors.append("atr is required for UNCONDITIONAL_DIRECTIONAL")
    return sorted(set(errors))
