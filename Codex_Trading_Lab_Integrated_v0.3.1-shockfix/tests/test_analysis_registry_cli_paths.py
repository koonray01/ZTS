from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.update_market_analysis as update_market_analysis
import tools.record_analysis_registry as record_cli
import tools.rebuild_analysis_registry as rebuild_cli
import tools.verify_analysis_registry as verify_cli
import tools.catch_up_analysis_registry as catchup_cli
import tools.backfill_analysis_registry_phase2 as backfill_cli
from ctl_analysis_registry.paths import CONFIG_SCHEMA_VERSION, PRODUCER_VERSION


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CONFIG_SCHEMA_VERSION,
                "canonical_root": str(tmp_path / "canonical"),
                "implementation_root": str(tmp_path / "implementation"),
                "producer_version": PRODUCER_VERSION,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_update_validates_registry_before_output_or_mt5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    output = tmp_path / "out"
    monkeypatch.setattr(
        update_market_analysis,
        "MetaTrader5SnapshotAdapter",
        lambda: calls.append("adapter"),
    )

    code = update_market_analysis.main(
        [
            "--output",
            str(output),
            "--registry-config",
            str(tmp_path / "missing.json"),
        ]
    )

    assert code != 0
    assert calls == []
    assert not output.exists()


def test_update_reports_resolved_registry_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)
    snapshot = {
        "snapshot_id": "S1",
        "symbol": "XAUUSD",
        "source": "LIVE_MT5",
        "capture_time": "2026-07-22T09:00:00+00:00",
        "freshness": {"status": "FRESH"},
        "qc": {"decision": "PASS"},
    }

    class Adapter:
        def capture(self, **kwargs):
            return snapshot

    monkeypatch.setattr(update_market_analysis, "MetaTrader5SnapshotAdapter", Adapter)
    monkeypatch.setattr(update_market_analysis, "EvidenceStore", lambda path: type("Store", (), {"write_raw_snapshot": lambda self, value: None})())
    monkeypatch.setattr(update_market_analysis, "run_decision_core", lambda value: {"generated_at": snapshot["capture_time"], "entry_packet": {"candidates": []}})
    monkeypatch.setattr(
        update_market_analysis,
        "register_analysis_and_catchup",
        lambda **kwargs: {"registry_recording_status": "RECORDED"},
    )

    code = update_market_analysis.main(
        ["--output", str(tmp_path / "out"), "--registry-config", str(config)]
    )
    response = json.loads(capsys.readouterr().out)

    assert code == 0
    assert response["registry_root"] == str((tmp_path / "canonical").resolve())
    assert response["registry_mode"] == "CANONICAL"
    assert response["registry_config_schema_version"] == CONFIG_SCHEMA_VERSION
    assert response["registry_producer_version"] == PRODUCER_VERSION


def test_record_uses_canonical_ledger_and_reports_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)
    output = tmp_path / "analysis"
    output.mkdir()
    observed: dict[str, Path] = {}

    def record(output_dir, ledger, source_class):
        observed["ledger"] = ledger.path
        return {"recorded": 1}

    monkeypatch.setattr(record_cli, "record_zenith_output", record)
    assert record_cli.main(["--output-dir", str(output), "--registry-config", str(config)]) == 0
    response = json.loads(capsys.readouterr().out)
    assert observed["ledger"] == (tmp_path / "canonical" / "events.jsonl").resolve()
    assert response["registry_mode"] == "CANONICAL"


def test_rebuild_and_verify_use_canonical_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)
    observed: dict[str, tuple[Path, Path | None]] = {}

    def rebuild(ledger, sqlite):
        observed["rebuild"] = (ledger, sqlite)
        return {"events": 0}

    def verify(ledger, sqlite):
        observed["verify"] = (ledger, sqlite)
        return {"status": "PASS"}

    monkeypatch.setattr(rebuild_cli, "rebuild_index", rebuild)
    monkeypatch.setattr(verify_cli, "verify_registry", verify)

    assert rebuild_cli.main(["--registry-config", str(config)]) == 0
    capsys.readouterr()
    assert verify_cli.main(["--registry-config", str(config)]) == 0
    capsys.readouterr()
    expected = (tmp_path / "canonical").resolve()
    assert observed["rebuild"] == (expected / "events.jsonl", expected / "index.sqlite")
    assert observed["verify"] == (expected / "events.jsonl", expected / "index.sqlite")


def test_catchup_and_backfill_clis_use_canonical_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)
    event = tmp_path / "event.json"
    bundle = tmp_path / "bundle.json"
    event.write_text("{}", encoding="utf-8")
    bundle.write_text("{}", encoding="utf-8")
    observed = {}

    monkeypatch.setattr(catchup_cli, "MetaTrader5SnapshotAdapter", object)
    def catchup(**kwargs):
        observed["catchup"] = kwargs
        return {"status": "COMPLETE"}

    def backfill(*args, **kwargs):
        observed["backfill"] = (args, kwargs)
        return {"classification": "INVALID_INPUT"}

    monkeypatch.setattr(catchup_cli, "run_catchup", catchup)
    monkeypatch.setattr(backfill_cli, "backfill_eligible", backfill)

    assert catchup_cli.main(["--registry-config", str(config)]) == 0
    capsys.readouterr()
    assert backfill_cli.main(["--event", str(event), "--source-bundle", str(bundle), "--registry-config", str(config)]) == 0
    capsys.readouterr()
    paths = observed["catchup"]["paths"]
    assert paths.root == (tmp_path / "canonical").resolve()
    assert observed["backfill"][1]["paths"] == paths


def test_verify_retains_explicit_read_only_inspection_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(tmp_path)
    external = tmp_path / "external"
    observed = {}

    def verify(ledger, sqlite):
        observed["paths"] = (ledger, sqlite)
        return {"status": "PASS"}

    monkeypatch.setattr(verify_cli, "verify_registry", verify)
    assert verify_cli.main([
        "--registry-config", str(config),
        "--ledger", str(external / "events.jsonl"),
        "--sqlite", str(external / "index.sqlite"),
    ]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["registry_mode"] == "NON_CANONICAL"
    assert observed["paths"] == (external / "events.jsonl", external / "index.sqlite")
