from __future__ import annotations

from datetime import datetime, timezone

import ctl_analysis_registry.integration as integration


NOW = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)


def test_current_analysis_is_frozen_before_bounded_catchup(monkeypatch, tmp_path) -> None:
    calls = []
    monkeypatch.setattr(integration, "register_current_analysis", lambda **kwargs: calls.append("record") or {"decision_ids": ["D1"], "scheduled": 1})
    monkeypatch.setattr(integration, "run_catchup", lambda **kwargs: calls.append("catchup") or {"status": "COMPLETE", "processed": 0, "remaining": 0})

    result = integration.register_analysis_and_catchup(
        decision_state={"snapshot_id": "S1"}, snapshot={"snapshot_id": "S1"}, analysis_id="A1",
        ledger_path=tmp_path / "events.jsonl", sqlite_path=tmp_path / "index.sqlite",
        evidence_root=tmp_path / "evidence", adapter=object(), now=NOW, max_jobs=5,
    )

    assert calls == ["record", "catchup"]
    assert result["registry_recording_status"] == "RECORDED"
    assert result["catchup_status"] == "COMPLETE"


def test_registry_integrity_failure_marks_analysis_unregistered(monkeypatch, tmp_path) -> None:
    def broken(**kwargs):
        raise ValueError("invalid registry")

    monkeypatch.setattr(integration, "register_current_analysis", broken)
    result = integration.register_analysis_and_catchup(
        decision_state={"snapshot_id": "S1"}, snapshot={"snapshot_id": "S1"}, analysis_id="A1",
        ledger_path=tmp_path / "events.jsonl", sqlite_path=tmp_path / "index.sqlite",
        evidence_root=tmp_path / "evidence", adapter=object(), now=NOW, max_jobs=5,
    )

    assert result["registry_recording_status"] == "ANALYSIS_NOT_REGISTERED"
    assert result["catchup_status"] == "BLOCKED"
    assert result["trade_write_enabled"] is False
    assert result["order_actions"] == 0


def test_legacy_incomplete_current_scenario_is_registered_but_not_scheduled(tmp_path) -> None:
    snapshot = {
        "snapshot_id": "S1", "symbol": "XAUUSD", "source": "LIVE_MT5",
        "capture_time": NOW.isoformat(), "qc": {"decision": "PASS"},
        "freshness": {"status": "FRESH"}, "evidence_refs": ["S1"],
    }
    decision = {
        "snapshot_id": "S1", "scenario_packet": {"scenarios": [
            {"scenario_id": "SC1", "rank": "PRIMARY", "direction": "RANGE", "status": "WATCHING"}
        ]},
        "entry_packet": {"candidates": []}, "market_packet": {},
    }

    result = integration.register_current_analysis(
        decision_state=decision, snapshot=snapshot, analysis_id="A1",
        ledger_path=tmp_path / "events.jsonl", sqlite_path=tmp_path / "index.sqlite", now=NOW,
    )

    assert len(result["decision_ids"]) == 1
    assert result["scheduled"] == 0
