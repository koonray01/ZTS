"""Conservative Phase 1 classification and opt-in Phase 2 backfill."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .ledger import AppendOnlyLedger
from .coordination import acquire_registry_writer
from .paths import RegistryPaths, resolve_registry_paths, validate_mutation_paths
from .recorder import record_frozen_decisions


BACKFILL_CLASSES = {
    "BACKFILL_ELIGIBLE",
    "NON_SCORABLE_LEGACY",
    "INVALID_INPUT",
    "INSUFFICIENT_EVIDENCE",
}


def _positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def classify_legacy_decision(event: dict[str, Any], source_bundle: dict[str, Any]) -> str:
    """Classify only explicit pre-outcome fields; never reconstruct prose."""

    if source_bundle.get("quarantined") or source_bundle.get("source_qc") not in {"PASS", "VERIFIED"}:
        return "INVALID_INPUT"
    if not source_bundle.get("frozen_before_outcome") or not source_bundle.get("evidence_refs"):
        return "INSUFFICIENT_EVIDENCE"
    if event.get("source_class") == "CHAT_ONLY":
        return "NON_SCORABLE_LEGACY"

    payload = event.get("payload")
    if not isinstance(payload, dict) or not payload.get("horizons"):
        return "NON_SCORABLE_LEGACY"
    decision_type = payload.get("decision_type")
    if decision_type == "DIRECTIONAL":
        measurable = (
            payload.get("direction") in {"BULLISH", "BEARISH"}
            and _positive_number(payload.get("reference_price"))
            and _positive_number(payload.get("atr"))
        )
    elif decision_type == "SCENARIO":
        measurable = bool(payload.get("event_steps")) and isinstance(payload.get("invalidation"), dict) and bool(payload.get("expiry_time"))
    elif decision_type == "SETUP":
        geometry = payload.get("setup_geometry")
        measurable = isinstance(geometry, dict) and all(geometry.get(key) is not None for key in ("entry", "stop", "scoring_target", "expiry_time"))
    elif decision_type == "ABSTENTION":
        measurable = bool(payload.get("control_definition"))
    else:
        return "INVALID_INPUT"
    return "BACKFILL_ELIGIBLE" if measurable else "NON_SCORABLE_LEGACY"


def backfill_eligible(
    event: dict[str, Any],
    source_bundle: dict[str, Any],
    ledger_path: str | Path,
    *,
    dry_run: bool = True,
    paths: RegistryPaths | None = None,
) -> dict[str, Any]:
    """Append only a supplied, already typed frozen decision after classification."""

    classification = classify_legacy_decision(event, source_bundle)
    result: dict[str, Any] = {
        "classification": classification,
        "created_decisions": 0,
        "proposed_event_ids": [],
        "dry_run": dry_run,
    }
    if classification != "BACKFILL_ELIGIBLE":
        return result
    frozen = source_bundle.get("frozen_decision")
    if not isinstance(frozen, dict):
        result["classification"] = "INSUFFICIENT_EVIDENCE"
        return result

    ledger = AppendOnlyLedger(ledger_path)
    if dry_run:
        result["proposed_event_ids"] = [frozen.get("decision_id")]
        return result

    paths = paths or resolve_registry_paths(Path(ledger_path).parent)
    validate_mutation_paths(paths, ledger_path=ledger_path)
    lease = acquire_registry_writer(paths, f"backfill-{uuid4().hex}", datetime.now(timezone.utc))
    try:
        event_ids = record_frozen_decisions(ledger, [frozen])
    finally:
        lease.release()
    result["created_decisions"] = len(event_ids)
    result["proposed_event_ids"] = event_ids
    return result
