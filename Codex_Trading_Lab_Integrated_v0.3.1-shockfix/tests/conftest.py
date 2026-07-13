from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_decision_core import run_decision_core
from ctl_permission_agent.jobs import build_codex_job
from ctl_codex_worker import ResultStore, StateRegistry, WorkerJobStore


@pytest.fixture
def root():
    return ROOT


@pytest.fixture
def now():
    return datetime(2025, 3, 6, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def snapshot(root):
    return json.loads(
        (root / "examples" / "snapshots" / "directional_market.snapshot.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture
def state(snapshot):
    decision = run_decision_core(snapshot)
    return {**decision, "snapshot": snapshot}


@pytest.fixture
def market_job(state, now):
    return build_codex_job(
        snapshot_id=state["snapshot_id"],
        event_types=["MARKET_STATE_CHANGED"],
        input_refs=[state["market_packet"]["market_packet_id"]],
        now=now,
    )


@pytest.fixture
def stores(tmp_path, state):
    registry = StateRegistry(tmp_path / "state.json")
    registry.put(state["snapshot_id"], state)
    return {
        "jobs": WorkerJobStore(tmp_path / "jobs.jsonl"),
        "results": ResultStore(tmp_path / "results.jsonl"),
        "registry": registry,
        "audit": tmp_path / "audit.jsonl",
    }


def final_turn(state, **overrides):
    payload = {
        "summary": "Deterministic state reviewed.",
        "facts": [
            {
                "claim": "A compact market packet is available.",
                "evidence_refs": [state["market_packet"]["market_packet_id"]],
            }
        ],
        "interpretations": [],
        "unknowns": [],
        "recommended_next_action": "WAIT",
        "permission_claim": "NOT_EVALUATED",
    }
    payload.update(overrides)
    return {
        "turn_type": "FINAL",
        "final": payload,
        "usage": {"input_tokens": 100, "output_tokens": 100},
    }
