from __future__ import annotations

import copy

from ctl_codex_worker import CodexWorker, ScriptedProvider
from ctl_codex_worker.result_store import verify_result_store
from conftest import final_turn


def make_worker(root, stores, provider_factory):
    return CodexWorker(
        worker_id="WORKER-1",
        job_store=stores["jobs"],
        result_store=stores["results"],
        state_registry=stores["registry"],
        skills_root=root / "skills",
        schemas_root=root / "schemas",
        audit_path=stores["audit"],
        provider_factory=provider_factory,
    )


def test_worker_success_without_tool(root, stores, market_job, state, now):
    stores["jobs"].enqueue(market_job, now=now)
    worker = make_worker(
        root,
        stores,
        lambda _job: ScriptedProvider(turns=[final_turn(state)]),
    )
    report = worker.run_once(now=now)
    assert report["status"] == "SUCCEEDED"
    assert report["result"]["permission_claim"] == "NOT_EVALUATED"
    assert report["result"]["auto_execution_enabled"] is False
    assert stores["jobs"].project()[market_job["job_id"]]["status"] == "SUCCEEDED"
    assert verify_result_store(stores["results"].path) == (True, [])


def test_worker_tool_then_final(root, stores, market_job, state, now):
    stores["jobs"].enqueue(market_job, now=now)
    turns = [
        {
            "turn_type": "TOOL_CALLS",
            "tool_calls": [
                {
                    "tool_call_id": "CALL-1",
                    "tool_name": "get_current_state",
                    "arguments": {},
                }
            ],
            "usage": {"input_tokens": 100, "output_tokens": 20},
        },
        final_turn(state),
    ]
    worker = make_worker(
        root,
        stores,
        lambda _job: ScriptedProvider(turns=copy.deepcopy(turns)),
    )
    report = worker.run_once(now=now)
    assert report["status"] == "SUCCEEDED"
    assert len(report["result"]["tool_trace_ids"]) == 1


def test_result_store_prevents_double_execution(root, stores, market_job, state, now):
    stores["jobs"].enqueue(market_job, now=now)
    provider_calls = {"count": 0}

    def provider(_job):
        provider_calls["count"] += 1
        return ScriptedProvider(turns=[final_turn(state)])

    worker = make_worker(root, stores, provider)
    first = worker.run_once(now=now)
    second = worker.run_once(now=now)
    assert first["status"] == "SUCCEEDED"
    assert second is None
    assert provider_calls["count"] == 1
