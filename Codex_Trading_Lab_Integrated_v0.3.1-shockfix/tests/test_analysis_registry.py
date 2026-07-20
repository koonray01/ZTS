from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

from ctl_analysis_registry.events import build_event, event_hash, validate_event_chain
from ctl_analysis_registry.identity import canonical_json, sha256_hex, stable_id
from ctl_analysis_registry.ledger import AppendOnlyLedger, LedgerCollisionError, LedgerError


ROOT = Path(__file__).resolve().parents[1]


def _schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def _bundle() -> dict:
    return {
        "schema_version": "ANALYSIS_REGISTRY_BUNDLE_V0_1",
        "analysis_id": "ANALYSIS_TEST_001",
        "source_class": "LIVE_MT5",
        "integrity_tier": "VERIFIED",
        "analysis": {"snapshot_id": "SNAP_TEST", "symbol": "XAUUSD"},
        "views": [
            {
                "view_id": "VIEW_TEST",
                "system": "ZENITH",
                "action": "HOLD",
                "model_fingerprint": "MODEL_TEST",
            }
        ],
        "decisions": [
            {
                "decision_id": "DECISION_TEST",
                "decision_type": "SCENARIO",
                "action": "HOLD",
                "scorable": True,
                "horizons": ["1h"],
            }
        ],
        "evidence_refs": ["SNAP_TEST"],
    }


def test_identity_canonical_json_is_sorted_and_compact() -> None:
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert canonical_json({"text": "ไทย"}) == '{"text":"ไทย"}'


def test_identity_stable_id_and_hash_are_deterministic() -> None:
    assert stable_id("ANALYSIS", "XAUUSD", "T0") == stable_id("ANALYSIS", "XAUUSD", "T0")
    assert stable_id("ANALYSIS", "XAUUSD", "T0") != stable_id("ANALYSIS", "XAUUSD", "T1")
    assert stable_id("ANALYSIS", "XAUUSD", "T0").startswith("ANALYSIS_")
    assert sha256_hex("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_schema_valid_bundle_passes_validation() -> None:
    validate(_bundle(), _schema("analysis_registry_bundle.schema.json"))


def test_bundle_unknown_top_level_field_is_rejected() -> None:
    invalid = _bundle()
    invalid["unexpected"] = True
    with pytest.raises(ValidationError):
        validate(invalid, _schema("analysis_registry_bundle.schema.json"))


def _event_payload(event_id: str, *, payload: dict | None = None) -> dict:
    return {
        "event_id": event_id,
        "event_type": "ANALYSIS_RECORDED",
        "event_time": "2026-07-20T09:00:00Z",
        "decision_time": "2026-07-20T09:00:00Z",
        "source_class": "LIVE_MT5",
        "integrity_tier": "VERIFIED",
        "producer": "test",
        "payload": payload or {"analysis_id": "ANALYSIS_TEST"},
    }


def test_event_chain_links_and_hashes_are_deterministic() -> None:
    first = build_event(_event_payload("E1"), previous_hash=None)
    second = build_event(_event_payload("E2"), previous_hash=first["event_hash"])

    assert first["previous_event_hash"] is None
    assert second["previous_event_hash"] == first["event_hash"]
    assert event_hash(first) == first["event_hash"]
    assert validate_event_chain([first, second]) == []


def test_tampered_event_is_rejected_by_chain_validation() -> None:
    event = build_event(_event_payload("E1"), previous_hash=None)
    event["payload"]["tampered"] = True

    errors = validate_event_chain([event])

    assert any("hash mismatch" in error for error in errors)


def test_ledger_append_is_idempotent_and_collision_safe(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    ledger = AppendOnlyLedger(path)
    first = build_event(_event_payload("E1"), previous_hash=None)

    assert ledger.append(first) == "E1"
    assert ledger.append(first) == "E1"
    assert len(ledger.read_all()) == 1

    collision = build_event(_event_payload("E1", payload={"different": True}), previous_hash=None)
    with pytest.raises(LedgerCollisionError):
        ledger.append(collision)
    assert len(ledger.read_all()) == 1


def test_ledger_rejects_stale_previous_hash(tmp_path: Path) -> None:
    ledger = AppendOnlyLedger(tmp_path / "events.jsonl")
    first = build_event(_event_payload("E1"), previous_hash=None)
    ledger.append(first)
    stale = build_event(_event_payload("E2"), previous_hash=None)

    with pytest.raises(LedgerError, match="previous_event_hash"):
        ledger.append(stale)


def _write_zenith_fixture(root: Path, *, with_manifest: bool = True) -> Path:
    output = root / "analysis"
    evidence = output / "evidence" / "raw"
    evidence.mkdir(parents=True)
    snapshot = {
        "snapshot_id": "SNAP_FIXTURE",
        "symbol": "XAUUSD",
        "source": "LIVE_MT5",
        "capture_time": "2026-07-20T09:00:00Z",
        "evidence_refs": ["SNAP_FIXTURE", "BAR_FIXTURE"],
        "qc": {"decision": "PASS"},
        "freshness": {"status": "FRESH"},
        "quote": {"bid": 4018.36, "ask": 4018.58},
    }
    decision = {
        "snapshot_id": "SNAP_FIXTURE",
        "generated_at": "2026-07-20T09:00:00Z",
        "market_packet": {"snapshot_id": "SNAP_FIXTURE", "market_state": []},
        "scenario_packet": {
            "scenarios": [
                {
                    "scenario_id": "SCN_FIXTURE",
                    "rank": "PRIMARY",
                    "label": "Balance persists",
                    "direction": "RANGE",
                    "status": "WATCHING",
                    "missing_events": ["CLOSED_BAR_RESOLUTION"],
                }
            ]
        },
        "entry_packet": {"snapshot_id": "SNAP_FIXTURE", "candidates": []},
        "operational_state": {"current_action": "WATCH"},
        "claim_ledger": {"evidence_refs": ["SNAP_FIXTURE"]},
    }
    delta = {
        "schema_version": "0.1.0",
        "audit_status": "PASS",
        "previous_snapshot_id": None,
        "current_snapshot_id": "SNAP_FIXTURE",
        "previous_count": 0,
        "current_count": 0,
        "new": [], "stable": [], "status_changed": [], "terminalized": [],
        "expired": [], "superseded": [], "semantic_deduplicated": [],
        "suppressed": [], "unexpected_disappearance": [],
        "unexpected_disappearance_count": 0, "duplicate_candidate_ids": [],
        "continuity_ok": True,
    }
    for name, value in (("snapshot.json", snapshot), ("decision_state.json", decision), ("candidate_delta.json", delta)):
        (output / name).write_text(json.dumps(value), encoding="utf-8")
    if with_manifest:
        (evidence / "manifest.json").write_text(json.dumps({"snapshot_id": "SNAP_FIXTURE", "sha256": "a" * 64}), encoding="utf-8")
    return output


def test_recorder_emits_bound_zenith_events_and_safety(tmp_path: Path) -> None:
    from ctl_analysis_registry.recorder import record_zenith_output

    output = _write_zenith_fixture(tmp_path)
    ledger = AppendOnlyLedger(tmp_path / "registry" / "events.jsonl")

    result = record_zenith_output(output, ledger)
    events = ledger.read_all()

    assert result["source_class"] == "LIVE_MT5"
    assert result["integrity_tier"] == "VERIFIED"
    assert result["analysis_id"].startswith("ANALYSIS_")
    assert len(events) == len(result["event_ids"])
    assert {event["event_type"] for event in events} == {"ANALYSIS_RECORDED", "VIEW_RECORDED", "DECISION_RECORDED"}
    assert all(event["payload"]["analysis_id"] == result["analysis_id"] for event in events)
    assert events[0]["payload"]["safety"] == {
        "trade_write_enabled": False,
        "auto_execution_enabled": False,
        "order_actions": 0,
        "permission_leakage": 0,
    }


def test_recorder_is_idempotent_and_missing_manifest_is_partial(tmp_path: Path) -> None:
    from ctl_analysis_registry.recorder import record_zenith_output

    output = _write_zenith_fixture(tmp_path, with_manifest=False)
    ledger = AppendOnlyLedger(tmp_path / "registry" / "events.jsonl")

    first = record_zenith_output(output, ledger)
    second = record_zenith_output(output, ledger)

    assert first["event_ids"] == second["event_ids"]
    assert first["integrity_tier"] == "PARTIAL"
    assert len(ledger.read_all()) == len(first["event_ids"])


def _record_fixture(tmp_path: Path) -> tuple[Path, dict]:
    from ctl_analysis_registry.recorder import record_zenith_output

    output = _write_zenith_fixture(tmp_path)
    ledger_path = tmp_path / "registry" / "events.jsonl"
    result = record_zenith_output(output, AppendOnlyLedger(ledger_path))
    return ledger_path, result


def test_sqlite_index_rebuilds_and_exposes_traceable_rows(tmp_path: Path) -> None:
    import sqlite3

    from ctl_analysis_registry.index import rebuild_index

    ledger_path, result = _record_fixture(tmp_path)
    sqlite_path = tmp_path / "registry" / "index.sqlite"

    counts = rebuild_index(ledger_path, sqlite_path)

    assert counts["events"] == len(result["event_ids"])
    with sqlite3.connect(sqlite_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"events", "analyses", "views", "decisions", "evidence_refs"} <= tables
        row = connection.execute(
            "SELECT analysis_id, source_class, integrity_tier FROM analyses WHERE analysis_id=?",
            (result["analysis_id"],),
        ).fetchone()
        assert row == (result["analysis_id"], "LIVE_MT5", "VERIFIED")


def test_sqlite_rebuild_is_repeatable_and_tamper_fails(tmp_path: Path) -> None:
    from ctl_analysis_registry.index import rebuild_index

    ledger_path, _ = _record_fixture(tmp_path)
    first_path = tmp_path / "registry" / "first.sqlite"
    second_path = tmp_path / "registry" / "second.sqlite"
    first = rebuild_index(ledger_path, first_path)
    second = rebuild_index(ledger_path, second_path)
    assert first == second

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("ANALYSIS_RECORDED", "VIEW_RECORDED")
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="invalid ledger"):
        rebuild_index(ledger_path, tmp_path / "registry" / "tampered.sqlite")


def test_registry_verifier_passes_valid_ledger_and_index(tmp_path: Path) -> None:
    from ctl_analysis_registry.index import rebuild_index
    from ctl_analysis_registry.verify import verify_registry

    ledger_path, _ = _record_fixture(tmp_path)
    sqlite_path = tmp_path / "registry" / "index.sqlite"
    rebuild_index(ledger_path, sqlite_path)

    report = verify_registry(ledger_path, sqlite_path)

    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["coverage"]["outcome_labeling"] == "DEFERRED_PHASE_2"
    assert report["safety"]["order_actions"] == 0


def test_registry_verifier_blocks_tamper_and_safety_violation(tmp_path: Path) -> None:
    from ctl_analysis_registry.verify import verify_registry

    ledger_path, _ = _record_fixture(tmp_path)
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["payload"]["safety"]["trade_write_enabled"] = True
    lines[0] = json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = verify_registry(ledger_path)

    assert report["status"] == "BLOCKED"
    assert any("hash" in error or "trade_write_enabled" in error for error in report["errors"])
