"""Rebuildable SQLite projections for the append-only registry ledger."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import validate

from .events import validate_event_chain
from .contracts import V2_SCHEMA_VERSION, validate_phase2_payload
from .ledger import LedgerError


ROOT = Path(__file__).resolve().parents[2]


def _schema() -> dict[str, Any]:
    return json.loads((ROOT / "schemas" / "analysis_registry_event.schema.json").read_text(encoding="utf-8"))


DDL = """
PRAGMA foreign_keys = ON;
CREATE TABLE projection_metadata (
    projection_schema_version TEXT NOT NULL,
    ledger_head_hash TEXT,
    event_count INTEGER NOT NULL
);
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    event_hash TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_time TEXT NOT NULL,
    decision_time TEXT,
    source_class TEXT NOT NULL,
    integrity_tier TEXT NOT NULL,
    previous_event_hash TEXT,
    payload_json TEXT NOT NULL
);
CREATE TABLE analyses (
    analysis_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    snapshot_id TEXT,
    symbol TEXT,
    source_class TEXT NOT NULL,
    integrity_tier TEXT NOT NULL,
    safety_json TEXT NOT NULL
);
CREATE TABLE views (
    view_id TEXT PRIMARY KEY,
    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
    event_id TEXT NOT NULL REFERENCES events(event_id),
    system TEXT NOT NULL,
    action TEXT NOT NULL
);
CREATE TABLE decisions (
    decision_id TEXT PRIMARY KEY,
    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
    view_id TEXT NOT NULL REFERENCES views(view_id),
    event_id TEXT NOT NULL REFERENCES events(event_id),
    decision_type TEXT NOT NULL,
    action TEXT NOT NULL,
    scorable INTEGER NOT NULL,
    horizons_json TEXT NOT NULL
);
CREATE TABLE evidence_refs (
    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
    event_id TEXT NOT NULL REFERENCES events(event_id),
    evidence_ref TEXT NOT NULL,
    PRIMARY KEY (analysis_id, event_id, evidence_ref)
);
CREATE TABLE frozen_decisions (
    decision_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    analysis_id TEXT NOT NULL,
    view_id TEXT NOT NULL,
    system TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    decision_subtype TEXT NOT NULL,
    prediction_family_id TEXT NOT NULL,
    semantic_opportunity_id TEXT,
    variant_id TEXT,
    decision_time TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE evaluation_jobs (
    job_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    decision_id TEXT NOT NULL,
    horizon TEXT NOT NULL,
    labeling_policy_version TEXT NOT NULL,
    state TEXT NOT NULL,
    due_at TEXT NOT NULL,
    terminal_reason TEXT,
    payload_json TEXT NOT NULL
);
CREATE TABLE followup_evidence (
    evidence_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    decision_id TEXT NOT NULL,
    horizon TEXT NOT NULL,
    price_quality TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE model_outcomes (
    outcome_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    decision_id TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    system TEXT NOT NULL,
    horizon TEXT NOT NULL,
    original_policy_version TEXT NOT NULL,
    classification TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX idx_events_analysis ON events(json_extract(payload_json, '$.analysis_id'));
CREATE INDEX idx_decisions_analysis ON decisions(analysis_id);
CREATE INDEX idx_evidence_analysis ON evidence_refs(analysis_id);
CREATE INDEX idx_jobs_due ON evaluation_jobs(state, due_at);
CREATE UNIQUE INDEX idx_jobs_identity ON evaluation_jobs(decision_id, horizon, labeling_policy_version);
CREATE UNIQUE INDEX idx_outcomes_identity ON model_outcomes(decision_id, horizon, original_policy_version);
"""


def _insert_event(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    connection.execute(
        """INSERT INTO events
        (event_id, event_hash, event_type, event_time, decision_time,
         source_class, integrity_tier, previous_event_hash, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event["event_id"], event["event_hash"], event["event_type"], event["event_time"],
            event.get("decision_time"), event["source_class"], event["integrity_tier"],
            event.get("previous_event_hash"), json.dumps(event["payload"], ensure_ascii=False, sort_keys=True),
        ),
    )


def _insert_projection(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    payload = event["payload"]
    event_type = event["event_type"]
    analysis_id = payload.get("analysis_id")
    if event_type == "ANALYSIS_RECORDED" and analysis_id:
        analysis = payload.get("analysis", {})
        connection.execute(
            "INSERT INTO analyses (analysis_id, event_id, snapshot_id, symbol, source_class, integrity_tier, safety_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                analysis_id, event["event_id"], payload.get("snapshot_id"), payload.get("symbol"),
                event["source_class"], event["integrity_tier"], json.dumps(payload.get("safety", {}), sort_keys=True),
            ),
        )
    elif event_type == "VIEW_RECORDED" and analysis_id:
        connection.execute(
            "INSERT INTO views (view_id, analysis_id, event_id, system, action) VALUES (?, ?, ?, ?, ?)",
            (payload["view_id"], analysis_id, event["event_id"], payload["system"], payload["action"]),
        )
    elif event_type == "DECISION_RECORDED" and analysis_id:
        connection.execute(
            "INSERT INTO decisions (decision_id, analysis_id, view_id, event_id, decision_type, action, scorable, horizons_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                payload["decision_id"], analysis_id, payload["view_id"], event["event_id"],
                payload["decision_type"], payload["action"], int(bool(payload["scorable"])),
                json.dumps(payload.get("horizons", []), sort_keys=True),
            ),
        )
    elif event_type == "DECISION_FROZEN":
        connection.execute(
            """INSERT INTO frozen_decisions
            (decision_id, event_id, analysis_id, view_id, system, decision_type,
             decision_subtype, prediction_family_id, semantic_opportunity_id,
             variant_id, decision_time, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["decision_id"], event["event_id"], payload["analysis_id"],
                payload["view_id"], payload["system"], payload["decision_type"],
                payload["decision_subtype"], payload["prediction_family_id"],
                payload.get("semantic_opportunity_id"), payload.get("variant_id"),
                payload["decision_time"], json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )
    elif event_type == "EVALUATION_JOB_SCHEDULED":
        connection.execute(
            """INSERT INTO evaluation_jobs
            (job_id, event_id, decision_id, horizon, labeling_policy_version,
             state, due_at, terminal_reason, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["job_id"], event["event_id"], payload["decision_id"],
                payload["horizon"], payload["labeling_policy_version"], payload["state"],
                payload["due_at"], payload.get("terminal_reason"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )
    elif event_type == "FOLLOWUP_EVIDENCE_RECORDED":
        connection.execute(
            """INSERT INTO followup_evidence
            (evidence_id, event_id, decision_id, horizon, price_quality, manifest_hash, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["evidence_id"], event["event_id"], payload["decision_id"],
                payload["horizon"], payload["price_quality"], payload["manifest_hash"],
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )
    elif event_type == "MODEL_OUTCOME_RECORDED":
        connection.execute(
            """INSERT INTO model_outcomes
            (outcome_id, event_id, decision_id, decision_type, system, horizon,
             original_policy_version, classification, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["outcome_id"], event["event_id"], payload["decision_id"],
                payload["decision_type"], payload["system"], payload["horizon"],
                payload["original_policy_version"], payload["classification"],
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )
    if analysis_id:
        for evidence_ref in payload.get("evidence_refs", []):
            connection.execute(
                "INSERT OR IGNORE INTO evidence_refs (analysis_id, event_id, evidence_ref) VALUES (?, ?, ?)",
                (analysis_id, event["event_id"], str(evidence_ref)),
            )


def rebuild_index(ledger_path: Path, sqlite_path: Path) -> dict[str, int]:
    """Validate the complete ledger and atomically rebuild its SQLite index."""

    from .ledger import AppendOnlyLedger

    events = AppendOnlyLedger(ledger_path).read_all()
    chain_errors = validate_event_chain(events)
    if chain_errors:
        raise LedgerError("invalid ledger: " + "; ".join(chain_errors))
    schema = _schema()
    for event in events:
        try:
            validate(event, schema)
        except Exception as exc:  # jsonschema raises several validation classes across versions.
            raise LedgerError(f"invalid event schema: {event.get('event_id')}") from exc
        if event.get("schema_version") == V2_SCHEMA_VERSION:
            payload_errors = validate_phase2_payload(event["event_type"], event["payload"])
            if payload_errors:
                raise LedgerError(
                    f"invalid event payload: {event.get('event_id')}: " + "; ".join(payload_errors)
                )

    sqlite_path = Path(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{sqlite_path.name}.", suffix=".tmp", dir=sqlite_path.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.executescript(DDL)
            for event in events:
                _insert_event(connection, event)
                _insert_projection(connection, event)
            ledger_head_hash = events[-1]["event_hash"] if events else None
            connection.execute(
                "INSERT INTO projection_metadata (projection_schema_version, ledger_head_hash, event_count) VALUES (?, ?, ?)",
                ("ANALYSIS_REGISTRY_PROJECTION_V0_2", ledger_head_hash, len(events)),
            )
            connection.commit()
            projected_count = int(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])
            metadata = connection.execute(
                "SELECT ledger_head_hash, event_count FROM projection_metadata"
            ).fetchone()
            if projected_count != len(events) or metadata != (ledger_head_hash, len(events)):
                raise LedgerError("projection does not match ledger head/count")
        finally:
            connection.close()
        os.replace(temporary, sqlite_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    with sqlite3.connect(sqlite_path) as connection:
        result = {}
        for table in (
            "events", "analyses", "views", "decisions", "evidence_refs",
            "frozen_decisions", "evaluation_jobs", "followup_evidence", "model_outcomes",
        ):
            result[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    return result
