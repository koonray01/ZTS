"""Fail-closed integrity and safety verification for the registry."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

from .events import validate_event_chain
from .contracts import V2_SCHEMA_VERSION, validate_phase2_payload
from .ledger import AppendOnlyLedger, LedgerError


ROOT = Path(__file__).resolve().parents[2]


def _schema() -> dict[str, Any]:
    return json.loads((ROOT / "schemas" / "analysis_registry_event.schema.json").read_text(encoding="utf-8"))


def _index_check(sqlite_path: Path, events: list[dict[str, Any]]) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    counts: dict[str, int] = {}
    required = {
        "events", "analyses", "views", "decisions", "evidence_refs",
        "projection_metadata", "frozen_decisions", "evaluation_jobs",
        "followup_evidence", "model_outcomes",
    }
    connection = sqlite3.connect(sqlite_path)
    try:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        missing = sorted(required - tables)
        if missing:
            return ["index missing tables: " + ", ".join(missing)], counts
        for table in sorted(required):
            counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        indexed = {
            row[0]: row[1]
            for row in connection.execute("SELECT event_id, event_hash FROM events")
        }
        expected = {event["event_id"]: event["event_hash"] for event in events}
        if indexed != expected:
            errors.append("index event hashes/count do not match ledger")
        metadata = connection.execute(
            "SELECT projection_schema_version, ledger_head_hash, event_count FROM projection_metadata"
        ).fetchall()
        expected_head = events[-1]["event_hash"] if events else None
        if metadata != [("ANALYSIS_REGISTRY_PROJECTION_V0_2", expected_head, len(events))]:
            errors.append("index projection metadata does not match ledger head/count")
    except sqlite3.Error as exc:
        errors.append(f"index read failure: {exc}")
    finally:
        connection.close()
    return errors, counts


def verify_registry(ledger_path: Path, sqlite_path: Path | None = None) -> dict[str, Any]:
    """Return PASS/CONDITIONAL/BLOCKED without mutating any artifact."""

    errors: list[str] = []
    warnings: list[str] = []
    try:
        events = AppendOnlyLedger(ledger_path).read_all()
    except LedgerError as exc:
        events = []
        errors.append(str(exc))

    errors.extend(validate_event_chain(events))
    schema = _schema()
    source_counts: Counter[str] = Counter()
    integrity_counts: Counter[str] = Counter()
    safety = {
        "trade_write_enabled": False,
        "auto_execution_enabled": False,
        "order_actions": 0,
        "permission_leakage": 0,
    }
    for event in events:
        try:
            validate(event, schema)
        except ValidationError:
            errors.append(f"event schema invalid: {event.get('event_id')}")
        if event.get("schema_version") == V2_SCHEMA_VERSION:
            payload_errors = validate_phase2_payload(
                str(event.get("event_type")),
                event.get("payload") if isinstance(event.get("payload"), dict) else {},
            )
            errors.extend(
                f"event payload invalid: {event.get('event_id')}: {error}"
                for error in payload_errors
            )
        source_class = event.get("source_class")
        integrity_tier = event.get("integrity_tier")
        if source_class not in {"LIVE_MT5", "REPLAY", "SYNTHETIC", "CHAT_ONLY"}:
            errors.append(f"unknown source class: {source_class}")
        else:
            source_counts[source_class] += 1
        if integrity_tier not in {"VERIFIED", "PARTIAL", "CHAT_ONLY", "UNMATCHED"}:
            errors.append(f"unknown integrity tier: {integrity_tier}")
        else:
            integrity_counts[integrity_tier] += 1
        payload_safety = event.get("payload", {}).get("safety", {})
        safety["trade_write_enabled"] = safety["trade_write_enabled"] or bool(payload_safety.get("trade_write_enabled", False))
        safety["auto_execution_enabled"] = safety["auto_execution_enabled"] or bool(payload_safety.get("auto_execution_enabled", False))
        safety["order_actions"] = max(safety["order_actions"], int(payload_safety.get("order_actions", 0) or 0))
        safety["permission_leakage"] = max(safety["permission_leakage"], int(payload_safety.get("permission_leakage", 0) or 0))
    if safety["trade_write_enabled"]:
        errors.append("safety violation: trade_write_enabled=true")
    if safety["auto_execution_enabled"]:
        errors.append("safety violation: auto_execution_enabled=true")
    if safety["order_actions"] != 0:
        errors.append(f"safety violation: order_actions={safety['order_actions']}")
    if safety["permission_leakage"] != 0:
        errors.append(f"safety violation: permission_leakage={safety['permission_leakage']}")

    index_counts: dict[str, int] = {}
    if sqlite_path is not None and not errors:
        index_errors, index_counts = _index_check(Path(sqlite_path), events)
        errors.extend(index_errors)
    elif sqlite_path is None:
        warnings.append("SQLite index was not supplied")

    if any(tier != "VERIFIED" for tier in integrity_counts):
        warnings.append("non-VERIFIED records are excluded from headline metrics")
    if not events:
        warnings.append("ledger has no events")
    if errors:
        status = "BLOCKED"
    elif warnings:
        status = "CONDITIONAL"
    else:
        status = "PASS"
    return {
        "status": status,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "counts": {"events": len(events), **index_counts},
        "safety": safety,
        "coverage": {
            "source_class": dict(sorted(source_counts.items())),
            "integrity_tier": dict(sorted(integrity_counts.items())),
            "outcome_labeling": "DEFERRED_PHASE_2",
            "headline_metrics_eligible": integrity_counts.get("VERIFIED", 0),
        },
    }
