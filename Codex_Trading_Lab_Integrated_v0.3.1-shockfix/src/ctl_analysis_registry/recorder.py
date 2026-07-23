"""Read-only conversion of Zenith output bundles into registry events."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import validate

from .contracts import validate_phase2_payload
from .events import build_event, build_v2_event
from .identity import canonical_json, sha256_hex, stable_id
from .ledger import AppendOnlyLedger


ROOT = Path(__file__).resolve().parents[2]
EVENT_SCHEMA = ROOT / "schemas" / "analysis_registry_event.schema.json"
BUNDLE_SCHEMA = ROOT / "schemas" / "analysis_registry_bundle.schema.json"
SOURCE_CLASSES = {"LIVE_MT5", "REPLAY", "SYNTHETIC", "CHAT_ONLY"}
INTEGRITY_TIERS = {"VERIFIED", "PARTIAL", "CHAT_ONLY", "UNMATCHED"}
VALID_ACTIONS = {"SETUP", "WATCH", "WAIT", "HOLD", "REJECT", "ABSTAIN"}
STRICTNESS_RR_FLOORS = {
    "EXPLORATORY": 0.50,
    "VERY_RELAXED": 0.75,
    "RELAXED": 1.00,
    "NORMAL": 1.50,
}
MATERIAL_REVISION_FIELDS = {
    "direction", "activation", "reference_price", "atr", "horizons", "rules",
    "labeling_policy_version", "setup_geometry",
}


def _decision_time(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("capture_time") or snapshot.get("last_tick_time") or "1970-01-01T00:00:00+00:00")


def _source_bindings(snapshot: dict[str, Any]) -> dict[str, Any]:
    refs = [str(item) for item in snapshot.get("evidence_refs", []) if item]
    return {
        "snapshot_id": str(snapshot.get("snapshot_id") or "UNKNOWN"),
        "manifest_hash": sha256_hex(canonical_json(snapshot)),
        "evidence_hashes": [sha256_hex(ref) for ref in refs] or [sha256_hex(str(snapshot.get("snapshot_id")))],
    }


def _quality(snapshot: dict[str, Any], *, scorable: bool) -> dict[str, Any]:
    qc = snapshot.get("qc", {}).get("decision")
    freshness = snapshot.get("freshness", {}).get("status")
    source_ok = qc == "PASS"
    fresh = freshness == "FRESH"
    return {
        "source_qc": "PASS" if source_ok else "FAIL" if qc else "UNKNOWN",
        "freshness": "FRESH" if fresh else "STALE" if freshness else "UNKNOWN",
        "integrity_tier": "VERIFIED" if source_ok and fresh else "PARTIAL",
        "scorable_status": "SCORABLE" if scorable and source_ok and fresh else "NON_SCORABLE",
    }


def _safety() -> dict[str, Any]:
    return {
        "trade_write_enabled": False,
        "auto_execution_enabled": False,
        "order_actions": 0,
        "permission_leakage": 0,
    }


def _role(value: Any) -> str:
    token = str(value or "NONE").upper()
    if token == "SECONDARY":
        return "ALTERNATIVE"
    return token if token in {"PRIMARY", "ALTERNATIVE", "CONTROL", "NONE"} else "NONE"


def _freeze_claim(
    claim: dict[str, Any],
    *,
    snapshot: dict[str, Any],
    analysis_id: str,
    view_id: str,
    system: str,
    engine_version: str,
) -> dict[str, Any]:
    decision_type = str(claim.get("decision_type") or "DIRECTIONAL").upper()
    subtype = str(claim.get("decision_subtype") or decision_type)
    horizons = [str(item) for item in claim.get("horizons", []) if item]
    semantic_root = str(
        claim.get("semantic_opportunity_id")
        or claim.get("opportunity_group_id")
        or claim.get("scenario_id")
        or claim.get("candidate_id")
        or claim.get("claim_id")
        or "GENERAL"
    )
    variant_id = claim.get("variant_id")
    policy = str(
        claim.get("labeling_policy_version")
        or ("DIRECTIONAL_TERMINAL_ATR_V1" if decision_type == "DIRECTIONAL" else "ORDERED_SCENARIO_V1" if decision_type == "SCENARIO" else "SINGLE_TARGET")
    )
    family_id = stable_id("PREDICTION_FAMILY", analysis_id, system, decision_type, semantic_root)
    decision_id = stable_id("DECISION_V2", family_id, variant_id, sha256_hex(canonical_json(sorted(horizons))), policy)
    decision_time = _decision_time(snapshot)
    missing: list[str] = []
    if not horizons:
        missing.append("MISSING_HORIZONS")
    rules = claim.get("rules") if isinstance(claim.get("rules"), dict) else None
    if decision_type == "SCENARIO":
        steps = claim.get("event_steps")
        if not isinstance(steps, list) or not steps:
            missing.append("MISSING_EVENT_STEPS")
        if not claim.get("expiry_time"):
            missing.append("MISSING_EXPIRY")
        if not isinstance(claim.get("invalidation"), dict):
            missing.append("MISSING_INVALIDATION")
        rules = {
            "success": steps or [], "failure": claim.get("invalidation") or {},
            "invalidation": claim.get("invalidation") or {}, "expiry": claim.get("expiry_time") or "UNKNOWN",
        }
    elif decision_type == "DIRECTIONAL":
        rules = rules or {
            "success": "SIGNED_RETURN_ATR_GTE_0_25", "failure": "SIGNED_RETURN_ATR_LTE_NEG_0_25",
            "invalidation": "SOURCE_BINDING_INVALID", "expiry": "HORIZON_END",
        }
        if subtype == "UNCONDITIONAL_DIRECTIONAL":
            if claim.get("reference_price") is None:
                missing.append("MISSING_REFERENCE_PRICE")
            atr = claim.get("atr")
            if not isinstance(atr, dict) or not atr.get("value"):
                missing.append("MISSING_ATR")
        elif subtype == "CONDITIONAL_DIRECTIONAL" and not isinstance(claim.get("activation"), dict):
            missing.append("MISSING_ACTIVATION")
    elif decision_type == "SETUP":
        for field in ("entry", "stop", "scoring_target", "expiry_time"):
            if claim.get(field) is None:
                missing.append(f"MISSING_{field.upper()}")
        side = str(claim.get("side") or "").upper()
        entry, stop, target = claim.get("entry"), claim.get("stop"), claim.get("scoring_target")
        if side not in {"BUY", "SELL"}:
            missing.append("INVALID_SETUP_SIDE")
        elif all(isinstance(value, (int, float)) for value in (entry, stop, target)):
            side_correct = (
                float(stop) < float(entry) < float(target)
                if side == "BUY"
                else float(target) < float(entry) < float(stop)
            )
            if not side_correct:
                missing.append("INVALID_SIDE_GEOMETRY")
            else:
                risk = abs(float(entry) - float(stop))
                reward = abs(float(target) - float(entry))
                strictness = str(claim.get("strictness") or "")
                floor = STRICTNESS_RR_FLOORS.get(strictness)
                if subtype == "CONDITIONAL_SETUP" and floor is None:
                    missing.append("INVALID_STRICTNESS")
                elif floor is not None and (risk <= 0 or reward / risk < floor):
                    missing.append("RR_BELOW_STRICTNESS_FLOOR")
        if subtype == "CONDITIONAL_SETUP":
            for field in (
                "activation",
                "activation_policy",
                "strictness",
                "generation_id",
                "geometry_provenance",
            ):
                if claim.get(field) is None:
                    missing.append(f"MISSING_{field.upper()}")
        rules = {
            "success": "SCORING_TARGET_FIRST", "failure": "STOP_FIRST",
            "invalidation": claim.get("invalidation") or "INVALID_INPUT",
            "expiry": claim.get("expiry_time") or "UNKNOWN",
        }
    else:
        rules = rules or {"success": "TARGET_FIRST", "failure": "STOP_FIRST", "invalidation": "INVALID_INPUT", "expiry": claim.get("expiry_time") or "UNKNOWN"}
    scorable = not missing
    quality = _quality(snapshot, scorable=scorable)
    if quality["scorable_status"] != "SCORABLE" and not missing:
        missing.append("SOURCE_QUALITY_NOT_SCORABLE")
    frozen: dict[str, Any] = {
        "decision_id": decision_id, "analysis_id": analysis_id, "view_id": view_id,
        "system": system, "decision_type": decision_type, "decision_subtype": subtype,
        "prediction_family_id": family_id, "semantic_opportunity_id": semantic_root,
        "variant_id": variant_id, "symbol": str(snapshot.get("symbol") or "UNKNOWN"),
        "direction": str(claim.get("direction") or "UNKNOWN").upper(),
        "action": _action(claim.get("action"), "WATCH"),
        "role": _role(claim.get("role") or claim.get("rank")),
        "decision_time": decision_time, "evaluation_start": decision_time,
        "horizons": horizons or ["UNSPECIFIED"], "labeling_policy_version": policy,
        "engine_version": engine_version,
        "timeframe_scope": [str(item) for item in claim.get("timeframe_scope", []) if item] or sorted({str(item.get("timeframe")) for item in claim.get("event_steps", []) if isinstance(item, dict) and item.get("timeframe")}) or ["UNKNOWN"],
        "rules": rules,
        "market_context": {
            "regime": str(claim.get("regime") or "UNKNOWN"),
            "volatility": str(claim.get("volatility") or "UNKNOWN"),
        },
        "source_bindings": _source_bindings(snapshot), "quality": quality,
        "non_scorable_reasons": sorted(set(missing)), "safety": _safety(),
        "source_class": str(snapshot.get("source") or "CHAT_ONLY"),
    }
    if subtype == "UNCONDITIONAL_DIRECTIONAL" and claim.get("reference_price") is not None:
        frozen["reference_price"] = {"method": "DECISION_TIME_MID", "value": float(claim["reference_price"])}
        frozen["atr"] = deepcopy(claim.get("atr"))
    elif subtype == "CONDITIONAL_DIRECTIONAL" and isinstance(claim.get("activation"), dict):
        frozen["activation"] = deepcopy(claim["activation"])
    if decision_type == "SETUP":
        frozen["setup_geometry"] = {
            "side": str(claim.get("side") or "UNKNOWN").upper(),
            "entry": claim.get("entry"), "stop": claim.get("stop"),
            "scoring_target": claim.get("scoring_target"),
            "expiry_time": claim.get("expiry_time"),
        }
        if subtype == "CONDITIONAL_SETUP":
            for field in (
                "activation",
                "activation_policy",
                "strictness",
                "generation_id",
                "geometry_provenance",
                "setup_horizon",
            ):
                if claim.get(field) is not None:
                    frozen[field] = deepcopy(claim[field])
    return frozen


def freeze_zenith_decisions(
    decision_state: dict[str, Any],
    snapshot: dict[str, Any],
    analysis_id: str,
) -> list[dict[str, Any]]:
    if decision_state.get("snapshot_id") != snapshot.get("snapshot_id"):
        raise ValueError("Zenith snapshot binding mismatch")
    view_id = stable_id("VIEW", analysis_id, "ZENITH")
    engine_version = str(decision_state.get("engine_version") or "ZENITH_UNKNOWN")
    market = decision_state.get("market_packet", {})
    frozen: list[dict[str, Any]] = []
    for scenario in decision_state.get("scenario_packet", {}).get("scenarios", []):
        claim = {
            **scenario,
            "decision_type": "SCENARIO",
            "decision_subtype": "ORDERED_EVENT_SCENARIO",
            "action": "WATCH" if scenario.get("status") in {"WATCHING", "ACTIVE"} else "ABSTAIN",
            "role": scenario.get("rank", "NONE"),
            "semantic_opportunity_id": scenario.get("opportunity_group_id") or scenario.get("scenario_id"),
            "timeframe_scope": sorted({str(step.get("timeframe")) for step in scenario.get("event_steps", []) if isinstance(step, dict) and step.get("timeframe")}),
            "regime": market.get("regime", "UNKNOWN"),
            "volatility": market.get("volatility", "UNKNOWN"),
        }
        frozen.append(_freeze_claim(claim, snapshot=snapshot, analysis_id=analysis_id, view_id=view_id, system="ZENITH", engine_version=engine_version))
    for candidate in decision_state.get("entry_packet", {}).get("candidates", []):
        claim = {
            **candidate,
            "decision_type": "SETUP",
            "decision_subtype": "SINGLE_TARGET_SETUP",
            "action": "SETUP",
            "role": candidate.get("role", "PRIMARY"),
            "semantic_opportunity_id": candidate.get("semantic_candidate_id") or candidate.get("candidate_id"),
            "timeframe_scope": [candidate.get("timeframe", "UNKNOWN")],
            "regime": market.get("regime", "UNKNOWN"),
            "volatility": market.get("volatility", "UNKNOWN"),
            "labeling_policy_version": "SINGLE_TARGET",
        }
        frozen.append(_freeze_claim(claim, snapshot=snapshot, analysis_id=analysis_id, view_id=view_id, system="ZENITH", engine_version=engine_version))
    return frozen


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def revise_decision(
    original: dict[str, Any],
    changes: dict[str, Any],
    *,
    revision_time: datetime,
) -> dict[str, Any]:
    material = bool(MATERIAL_REVISION_FIELDS & changes.keys())
    evaluation_start = _parse_time(str(original["evaluation_start"]))
    if material and revision_time >= evaluation_start:
        return {
            "decision_id": original["decision_id"],
            "original_decision_id": original["decision_id"],
            "revision_type": "AUDIT_ONLY_LATE_CORRECTION",
            "revision_time": revision_time.isoformat(),
            "proposed_changes": deepcopy(changes),
        }
    revised = deepcopy(original)
    revised.update(deepcopy(changes))
    revised["original_decision_id"] = original["decision_id"]
    revised["revision_time"] = revision_time.isoformat()
    revised["revision_type"] = "MATERIAL_REVISION" if material else "NON_MATERIAL_CORRECTION"
    if material:
        revised["decision_id"] = stable_id("DECISION_REVISION", original["decision_id"], canonical_json(changes), revision_time.isoformat())
    return revised


def record_frozen_decisions(
    ledger: AppendOnlyLedger,
    decisions: list[dict[str, Any]],
) -> list[str]:
    event_ids: list[str] = []
    for decision in decisions:
        payload_errors = validate_phase2_payload("DECISION_FROZEN", decision)
        if payload_errors:
            raise ValueError("invalid frozen decision: " + "; ".join(payload_errors))
        event_id = stable_id("EVENT", "DECISION_FROZEN", decision["decision_id"])
        existing = next((item for item in ledger.read_all() if item.get("event_id") == event_id), None)
        if existing is not None:
            event_ids.append(ledger.append_fsynced(existing))
            continue
        events = ledger.read_all()
        previous_hash = events[-1]["event_hash"] if events else None
        event = build_v2_event(
            {
                "event_id": event_id, "event_type": "DECISION_FROZEN",
                "event_time": decision["decision_time"], "decision_time": decision["decision_time"],
                "source_class": decision["source_class"],
                "integrity_tier": decision["quality"]["integrity_tier"],
                "producer": "ctl_analysis_registry.recorder", "payload": decision,
            },
            previous_hash=previous_hash,
        )
        event_ids.append(ledger.append_fsynced(event))
    return event_ids


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
