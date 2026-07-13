from __future__ import annotations

import importlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_all_integrated_packages_import():
    packages = [
        "ctl_eyes",
        "ctl_advanced_eyes",
        "ctl_decision_core",
        "ctl_permission_agent",
        "ctl_live_runtime",
        "ctl_replay_training",
        "ctl_knowledge_learning",
        "ctl_codex_worker",
        "ctl_mt5_snapshot",
    ]
    for package in packages:
        assert importlib.import_module(package) is not None


def test_all_current_schemas_parse():
    schemas = list((ROOT / "schemas").glob("*.json"))
    assert len(schemas) >= 10
    for path in schemas:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("$schema")


def test_all_expected_cli_tools_exist():
    expected = {
        "run_eyes.py",
        "run_advanced_eyes.py",
        "run_decision_core.py",
        "run_permission_agent.py",
        "run_live_session.py",
        "run_replay_case.py",
        "list_cases.py",
        "run_learning_cycle.py",
        "create_change_proposal.py",
        "run_worker_dry_run.py",
        "run_all_validation.py",
        "run_mt5_snapshot.py",
        "run_sprint10_harness.py",
        "run_forward_shadow.py",
        "bundle_sprint10_evidence.py",
    }
    assert expected <= {path.name for path in (ROOT / "tools").glob("*.py")}


def test_source_packs_preserved():
    inventory = json.loads((ROOT / "SOURCE_PACKS.json").read_text(encoding="utf-8"))
    assert len(inventory["packs"]) == 10
    assert all(item["file_count"] > 0 for item in inventory["packs"])


def test_no_trade_write_capability_in_current_runtime():
    forbidden = (
        "order_send",
        "TRADE_ACTION",
        "PositionClose",
        "PositionModify",
        "shell=True",
        "os.system",
        "subprocess.Popen",
    )
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for folder in [ROOT / "src", ROOT / "tools"]
        for path in folder.rglob("*.py")
    )
    for token in forbidden:
        assert token not in text
