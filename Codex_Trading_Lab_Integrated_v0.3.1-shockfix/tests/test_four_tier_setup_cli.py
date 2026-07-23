from __future__ import annotations

import json

import tools.update_market_analysis as cli
from ctl_analysis_registry.paths import CONFIG_SCHEMA_VERSION, PRODUCER_VERSION


def test_cli_four_tier_flag_registers_one_envelope(monkeypatch, tmp_path) -> None:
    config = tmp_path / "registry.json"
    config.write_text(json.dumps({
        "schema_version": CONFIG_SCHEMA_VERSION,
        "canonical_root": str(tmp_path / "registry"),
        "implementation_root": str(tmp_path / "implementation"),
        "producer_version": PRODUCER_VERSION,
    }), encoding="utf-8")
    snapshot = {
        "snapshot_id": "SNAP_CLI_1", "symbol": "XAUUSD", "source": "LIVE_MT5",
        "capture_time": "2026-07-23T14:00:00Z",
        "quote": {"bid": 4049.9, "ask": 4050.1},
        "qc": {"decision": "PASS"}, "freshness": {"status": "FRESH"},
        "evidence_refs": ["E1"],
        "terminal": {"connected": True, "trade_write_enabled": False},
    }
    decision = {
        "snapshot_id": snapshot["snapshot_id"], "generated_at": snapshot["capture_time"],
        "entry_packet": {"candidates": []},
        "market_packet": {
            "risk_flags": [],
            "market_state": [
                {"timeframe": tf, "regime": "TREND", "structure": "BEARISH", "volatility": "NORMAL"}
                for tf in ("M5", "M15", "H1", "H4")
            ],
            "active_zones": [
                {"zone_id": f"{tf}_{kind}", "timeframe": tf, "zone_type": kind,
                 "lower": lower, "upper": upper, "status": "ACTIVE"}
                for tf, kind, lower, upper in (
                    ("M5", "DEMAND", 4038, 4040), ("M5", "SUPPLY", 4052, 4054),
                    ("M15", "DEMAND", 4028, 4031), ("M15", "SUPPLY", 4060, 4063),
                    ("H1", "DEMAND", 4010, 4015), ("H1", "SUPPLY", 4080, 4085),
                    ("H4", "DEMAND", 3990, 4000), ("H4", "SUPPLY", 4100, 4110),
                )
            ],
        },
    }
    captured = {}

    class Adapter:
        def capture(self, **kwargs):
            return snapshot

    monkeypatch.setattr(cli, "MetaTrader5SnapshotAdapter", Adapter)
    monkeypatch.setattr(cli, "EvidenceStore", lambda path: type(
        "Store", (), {"write_raw_snapshot": lambda self, value: None}
    )())
    monkeypatch.setattr(cli, "run_decision_core", lambda value: decision)
    monkeypatch.setattr(
        cli, "register_analysis_and_catchup",
        lambda **kwargs: captured.update(kwargs) or {
            "registry_recording_status": "RECORDED", "scheduled_jobs": 16,
            "catchup_status": "COMPLETE", "catchup_processed": 0,
            "catchup_remaining": 16,
        },
    )

    result = cli.main_for_test([
        "--output", str(tmp_path / "out"), "--symbol", "XAUUSD", "--bars", "120",
        "--registry-config", str(config), "--four-tier-setups",
    ])

    assert len(captured["chat_envelope"]["claims"]) == 16
    assert result["setup_class"] == "CONDITIONAL_WATCH_SETUP"
    assert result["setup_variant_count"] == 16
    assert (tmp_path / "out" / "conditional_setups.json").exists()
    assert result["trade_write_enabled"] is False
    assert result["order_actions"] == 0
