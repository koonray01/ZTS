from __future__ import annotations

from pathlib import Path

from tools.inventory_analysis_registries import inventory_registries


def test_inventory_reports_split_registries_without_mutation(tmp_path: Path) -> None:
    legacy = tmp_path / "checkout" / "outputs" / "analysis_registry"
    legacy.mkdir(parents=True)
    ledger = legacy / "events.jsonl"
    ledger.write_text("{}\n", encoding="utf-8")
    before = ledger.read_bytes()
    modified = ledger.stat().st_mtime_ns

    report = inventory_registries([tmp_path], tmp_path / "runtime" / "analysis_registry")

    assert report["registries"][0]["canonical"] is False
    assert report["registries"][0]["ledger_bytes"] == len(before)
    assert report["mutation_performed"] is False
    assert ledger.read_bytes() == before
    assert ledger.stat().st_mtime_ns == modified
