from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


WORKSPACE = Path(r"D:\MyWork\AlgoTrade\OS\Zenith Trading System")
LAUNCHER = WORKSPACE / "tools" / "run_zenith_analysis.ps1"


@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell unavailable")
def test_launcher_resolves_same_root_from_checkout_and_worktree() -> None:
    project = WORKSPACE / "Codex_Trading_Lab_Integrated_v0.3.1-shockfix"
    worktree = WORKSPACE / ".worktrees" / "live-analysis-main" / "Codex_Trading_Lab_Integrated_v0.3.1-shockfix"
    outputs = []
    for cwd in (project, worktree):
        run = subprocess.run(
            ["powershell", "-NoProfile", "-File", str(LAUNCHER), "-ResolveOnly"],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=True,
        )
        outputs.append(json.loads(run.stdout))

    assert outputs[0] == outputs[1]
    assert outputs[0]["registry_root"] == str((WORKSPACE / "runtime" / "analysis_registry").resolve())
    assert Path(outputs[0]["implementation_root"]).is_absolute()
    assert outputs[0]["registry_mode"] == "CANONICAL"
