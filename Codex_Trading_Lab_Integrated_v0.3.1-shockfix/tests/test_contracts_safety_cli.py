from __future__ import annotations

import json
import subprocess
import sys

from jsonschema import Draft202012Validator, FormatChecker

from ctl_codex_worker import ScriptedProvider
from ctl_codex_worker.context import build_context
from ctl_codex_worker.skill_loader import SkillLoader
from conftest import final_turn


def validate(root, name, payload):
    schema = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
    return list(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(payload)
    )


def test_worker_turn_schema(root, state):
    assert validate(root, "worker_turn.schema.json", final_turn(state)) == []


def test_worker_context_schema(root, market_job, state):
    skill = SkillLoader(root / "skills").load(
        market_job["skill_id"], market_job["skill_version"]
    )
    context = build_context(
        job=market_job,
        skill=skill,
        state=state,
        effective_tools=skill["manifest"]["allowed_tools"],
        max_tool_calls=4,
    )
    assert validate(root, "worker_context.schema.json", context) == []


def test_runtime_has_no_trade_write_shell_or_live_provider(root):
    forbidden = (
        "order_send",
        "TRADE_ACTION",
        "PositionClose",
        "PositionModify",
        "shell=True",
        "os.system",
        "subprocess.Popen",
        "api_key=",
        "Authorization:",
    )
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for folder in [root / "src", root / "tools"]
        for path in folder.rglob("*.py")
    )
    for token in forbidden:
        assert token not in text


def test_worker_cli(root, tmp_path):
    output = tmp_path / "worker"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "run_worker_dry_run.py"),
            "--snapshot",
            str(root / "examples" / "snapshots" / "directional_market.snapshot.json"),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["worker_status"] == "SUCCEEDED"
    assert summary["permission_claim"] == "NOT_EVALUATED"
    assert summary["live_provider_connected"] is False
    assert summary["auto_execution_enabled"] is False
    assert summary["job_store_integrity"] is True
    assert summary["result_store_integrity"] is True
    assert summary["audit_integrity"] is True
