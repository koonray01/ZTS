"""Read-only conversion of Zenith output bundles into registry events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import validate

from .events import build_event
from .identity import stable_id
from .ledger import AppendOnlyLedger


ROOT = Path(__file__).resolve().parents[2]
EVENT_SCHEMA = ROOT / "schemas" / "analysis_registry_event.schema.json"
BUNDLE_SCHEMA = ROOT / "schemas" / "analysis_registry_bundle.schema.json"
SOURCE_CLASSES = {"LIVE_MT5", "REPLAY", "SYNTHETIC", "CHAT_ONLY"}
INTEGRITY_TIERS = {"VERIFIED", "PARTIAL", "CHAT_ONLY", "UNMATCHED"}
VALID_ACTIONS = {"SETUP", "WATCH", "WAIT", "HOLD", "REJECT", "ABSTAIN"}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact is not an object: {path}")
    return value


def _schema(name: str) -> dict[str, Any]:
    return _read_json(ROOT / "schemas" / name)


def _event_time(snapshot: dict[str, Any], decision: dict[str, Any]) -> str:
    return str(
        decision.get("generated_at")
        or snapshot.get("capture_time")
        or snapshot.get("last_tick_time")
        or "1970-01-01T00:00:00Z"
    )


def _evidence_refs(snapshot: dict[str, Any], decision: dict[str, Any]) -> list[str]:
    refs: set[str] = set(str(item) for item in snapshot.get("evidence_refs", []) if item)
    refs.update(str(item) for item in decision.get("claim_ledger", {}).get("evidence_refs", []) if item)
    refs.add(str(snapshot.get("snapshot_id")))
    return sorted(ref for ref in refs if ref and ref != "None")


def _manifest_info(output_dir: Path) -> tuple[bool, list[str]]:
    paths = sorted(output_dir.rglob("manifest.json"))
    valid: list[str] = []
    for path in paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            valid.append(str(path))
    return bool(valid), valid


def _classify_integrity(
    output_dir: Path,
    snapshot: dict[str, Any],
    decision: dict[str, Any],
    delta: dict[str, Any],
    refs: list[str],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    manifest_present, _ = _manifest_info(output_dir)
    if not snapshot or not decision:
        return "UNMATCHED", ["MISSING_SNAPSHOT_OR_DECISION"]
    if decision.get("snapshot_id") != snapshot.get("snapshot_id"):
        reasons.append("SNAPSHOT_BINDING_MISMATCH")
    if not delta:
        reasons.append("MISSING_CANDIDATE_DELTA")
    if not refs:
        reasons.append("MISSING_EVIDENCE_REFS")
    if not manifest_present:
        reasons.append("MISSING_VALID_MANIFEST")
    if snapshot.get("qc", {}).get("decision") != "PASS":
        reasons.append("SNAPSHOT_QC_NOT_PASS")
    if reasons:
        return "PARTIAL", sorted(set(reasons))
    return "VERIFIED", []


def _action(value: Any, default: str = "ABSTAIN") -> str:
    candidate = str(value or default).upper()
    return candidate if candidate in VALID_ACTIONS else default


def _append_event(
    ledger: AppendOnlyLedger,
    *,
    analysis_id: str,
    event_type: str,
    entity_id: str,
    event_time: str,
    decision_time: str,
    source_class: str,
    integrity_tier: str,
    payload: dict[str, Any],
) -> str:
    event_id = stable_id("EVENT", analysis_id, event_type, entity_id)
    existing = next((item for item in ledger.read_all() if item.get("event_id") == event_id), None)
    previous_hash = existing.get("previous_event_hash") if existing else (
        ledger.read_all()[-1].get("event_hash") if ledger.read_all() else None
    )
    event = build_event(
        {
            "event_id": event_id,
            "event_type": event_type,
            "event_time": event_time,
            "decision_time": decision_time,
            "source_class": source_class,
            "integrity_tier": integrity_tier,
            "producer": "ctl_analysis_registry.recorder",
            "payload": payload,
        },
        previous_hash=previous_hash,
    )
    # jsonschema validation happens before the event reaches durable storage.
    validate(event, _schema("analysis_registry_event.schema.json"))
    return ledger.append(event)


def record_zenith_output(
    output_dir: Path,
    ledger: AppendOnlyLedger,
    source_class: str | None = None,
) -> dict[str, Any]:
    """Record one Zenith output directory without modifying its artifacts."""

    output_dir = Path(output_dir)
    snapshot = _read_json(output_dir / "snapshot.json")
    decision = _read_json(output_dir / "decision_state.json")
    delta_path = output_dir / "candidate_delta.json"
    delta = _read_json(delta_path) if delta_path.exists() else {}
    symbol = str(snapshot.get("symbol") or "UNKNOWN")
    decision_time = _event_time(snapshot, decision)
    event_time = decision_time
    declared_source = str(source_class or snapshot.get("source") or "CHAT_ONLY").upper()
    if declared_source not in SOURCE_CLASSES:
        raise ValueError(f"unknown source class: {declared_source}")
    refs = _evidence_refs(snapshot, decision)
    integrity_tier, integrity_reasons = _classify_integrity(output_dir, snapshot, decision, delta, refs)
    if integrity_tier not in INTEGRITY_TIERS:
        raise ValueError(f"invalid integrity tier: {integrity_tier}")
    analysis_id = stable_id("ANALYSIS", snapshot.get("snapshot_id", "UNKNOWN"), decision_time, symbol)
    safety = {
        "trade_write_enabled": bool(decision.get("trade_write_enabled", False)),
        "auto_execution_enabled": bool(decision.get("auto_execution_enabled", False)),
        "order_actions": int(decision.get("order_actions", 0) or 0),
        "permission_leakage": int(decision.get("permission_leakage", 0) or 0),
    }
    common = {
        "analysis_id": analysis_id,
        "snapshot_id": snapshot.get("snapshot_id"),
        "symbol": symbol,
        "source_path": str(output_dir),
        "evidence_refs": refs,
        "integrity_reasons": integrity_reasons,
        "safety": safety,
    }
    event_ids: list[str] = []
    event_ids.append(
        _append_event(
            ledger,
            analysis_id=analysis_id,
            event_type="ANALYSIS_RECORDED",
            entity_id=analysis_id,
            event_time=event_time,
            decision_time=decision_time,
            source_class=declared_source,
            integrity_tier=integrity_tier,
            payload={
                **common,
                "analysis": {
                    "quote": snapshot.get("quote"),
                    "freshness": snapshot.get("freshness"),
                    "qc": snapshot.get("qc"),
                    "manifest_paths": _manifest_info(output_dir)[1],
                },
            },
        )
    )
    view_id = stable_id("VIEW", analysis_id, "ZENITH")
    current_action = _action(decision.get("operational_state", {}).get("current_action"))
    event_ids.append(
        _append_event(
            ledger,
            analysis_id=analysis_id,
            event_type="VIEW_RECORDED",
            entity_id=view_id,
            event_time=event_time,
            decision_time=decision_time,
            source_class=declared_source,
            integrity_tier=integrity_tier,
            payload={**common, "view_id": view_id, "system": "ZENITH", "action": current_action},
        )
    )

    decisions: list[dict[str, Any]] = []
    plan_decision = {
        "decision_id": stable_id("DECISION", analysis_id, "ACTION_PLAN"),
        "decision_type": "ACTION_PLAN",
        "action": current_action,
        "scorable": False,
        "horizons": [],
        "source": decision.get("operational_state", {}),
    }
    decisions.append(plan_decision)
    for scenario in decision.get("scenario_packet", {}).get("scenarios", []):
        scenario_id = str(scenario.get("scenario_id") or stable_id("SCENARIO", analysis_id, str(len(decisions))))
        decisions.append(
            {
                "decision_id": stable_id("DECISION", analysis_id, scenario_id),
                "decision_type": "SCENARIO",
                "action": _action("WATCH" if scenario.get("status") in {"WATCHING", "ACTIVE"} else "ABSTAIN"),
                "scorable": True,
                "horizons": ["1h"],
                "scenario": scenario,
            }
        )
    for candidate in decision.get("entry_packet", {}).get("candidates", []):
        candidate_id = str(candidate.get("candidate_id") or stable_id("CANDIDATE", analysis_id, str(len(decisions))))
        decisions.append(
            {
                "decision_id": stable_id("DECISION", analysis_id, candidate_id),
                "decision_type": "SETUP",
                "action": "SETUP",
                "scorable": True,
                "horizons": ["SCALPING"],
                "candidate": candidate,
            }
        )
    for item in decisions:
        decision_id = str(item["decision_id"])
        event_ids.append(
            _append_event(
                ledger,
                analysis_id=analysis_id,
                event_type="DECISION_RECORDED",
                entity_id=decision_id,
                event_time=event_time,
                decision_time=decision_time,
                source_class=declared_source,
                integrity_tier=integrity_tier,
                payload={**common, "view_id": view_id, **item},
            )
        )

    delta_groups = (
        ("new", delta.get("new", [])),
        ("status_changed", delta.get("status_changed", [])),
        ("terminalized", delta.get("terminalized", [])),
        ("expired", delta.get("expired", [])),
        ("superseded", delta.get("superseded", [])),
        ("semantic_deduplicated", delta.get("semantic_deduplicated", [])),
        ("suppressed", delta.get("suppressed", [])),
        ("unexpected_disappearance", delta.get("unexpected_disappearance", [])),
    )
    for category, items in delta_groups:
        for position, item in enumerate(items):
            candidate_id = str(item.get("candidate_id") if isinstance(item, dict) else item)
            entity_id = f"{category}:{candidate_id}:{position}"
            event_ids.append(
                _append_event(
                    ledger,
                    analysis_id=analysis_id,
                    event_type="CANDIDATE_STATUS_CHANGED",
                    entity_id=entity_id,
                    event_time=event_time,
                    decision_time=decision_time,
                    source_class=declared_source,
                    integrity_tier=integrity_tier,
                    payload={**common, "candidate_delta_category": category, "candidate": item},
                )
            )

    return {
        "analysis_id": analysis_id,
        "event_ids": event_ids,
        "source_class": declared_source,
        "integrity_tier": integrity_tier,
        "integrity_reasons": integrity_reasons,
        "evidence_refs": refs,
        "safety": safety,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
