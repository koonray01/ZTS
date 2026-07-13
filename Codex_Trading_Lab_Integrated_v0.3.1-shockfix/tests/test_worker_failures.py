from __future__ import annotations

import copy
from datetime import timedelta

from ctl_codex_worker import CodexWorker, ScriptedProvider
from ctl_codex_worker.provider import ProviderError
from conftest import final_turn


def worker(root, stores, factory, **kwargs):
    return CodexWorker(
        worker_id="WORKER-FAIL",
        job_store=stores["jobs"],
        result_store=stores["results"],
        state_registry=stores["registry"],
        skills_root=root / "skills",
        schemas_root=root / "schemas",
        audit_path=stores["audit"],
        provider_factory=factory,
        **kwargs,
    )


def test_retryable_provider_error_goes_retry_wait(
    root, stores, market_job, state, now
):
    stores["jobs"].enqueue(market_job, now=now)
    report = worker(
        root,
        stores,
        lambda _job: ScriptedProvider(
            turns=[final_turn(state)],
            fail_at_call=1,
            retryable_failure=True,
        ),
    ).run_once(now=now)
    assert report["status"] == "RETRY_WAIT"
    assert report["error"]["retryable"] is True


def test_permanent_provider_error_goes_dead_letter(
    root, stores, market_job, state, now
):
    stores["jobs"].enqueue(market_job, now=now)
    report = worker(
        root,
        stores,
        lambda _job: ScriptedProvider(
            turns=[final_turn(state)],
            fail_at_call=1,
            retryable_failure=False,
        ),
    ).run_once(now=now)
    assert report["status"] == "DEAD_LETTER"


def test_disallowed_tool_dead_letters(root, stores, market_job, state, now):
    stores["jobs"].enqueue(market_job, now=now)
    turns = [
        {
            "turn_type": "TOOL_CALLS",
            "tool_calls": [
                {
                    "tool_call_id": "BAD-1",
                    "tool_name": "run_part3",
                    "arguments": {
                        "candidate_id": "X",
                        "account": {},
                        "dependency_state": {},
                    },
                }
            ],
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
    ]
    report = worker(
        root,
        stores,
        lambda _job: ScriptedProvider(turns=copy.deepcopy(turns)),
    ).run_once(now=now)
    assert report["status"] == "DEAD_LETTER"
    assert report["error"]["code"] == "DISALLOWED_TOOL"


def test_token_budget_dead_letters(root, stores, market_job, state, now):
    low_budget_job = copy.deepcopy(market_job)
    low_budget_job["job_id"] = "JOB-LOW-TOKEN"
    low_budget_job["token_budget"] = 128
    stores["jobs"].enqueue(low_budget_job, now=now)
    report = worker(
        root,
        stores,
        lambda _job: ScriptedProvider(
            turns=[
                {
                    **final_turn(state),
                    "usage": {"input_tokens": 100, "output_tokens": 100},
                }
            ]
        ),
    ).run_once(now=now)
    assert report["status"] == "DEAD_LETTER"
    assert report["error"]["code"] == "TOKEN_BUDGET_EXCEEDED"


def test_invalid_final_schema_dead_letters(root, stores, market_job, state, now):
    stores["jobs"].enqueue(market_job, now=now)
    bad = final_turn(state)
    del bad["final"]["summary"]
    report = worker(
        root,
        stores,
        lambda _job: ScriptedProvider(turns=[bad]),
    ).run_once(now=now)
    assert report["status"] == "DEAD_LETTER"
    assert report["error"]["code"] == "INVALID_WORKER_RESULT"


def test_fabricated_permission_dead_letters(root, stores, market_job, state, now):
    stores["jobs"].enqueue(market_job, now=now)
    report = worker(
        root,
        stores,
        lambda _job: ScriptedProvider(
            turns=[final_turn(state, permission_claim="APPROVED")]
        ),
    ).run_once(now=now)
    assert report["status"] == "DEAD_LETTER"
    assert report["error"]["code"] == "FABRICATED_PERMISSION"


def test_skill_version_mismatch_dead_letters(
    root, stores, market_job, state, now
):
    bad_job = copy.deepcopy(market_job)
    bad_job["job_id"] = "JOB-BAD-SKILL"
    bad_job["skill_version"] = "9.9.9"
    stores["jobs"].enqueue(bad_job, now=now)
    report = worker(
        root,
        stores,
        lambda _job: ScriptedProvider(turns=[final_turn(state)]),
    ).run_once(now=now)
    assert report["status"] == "DEAD_LETTER"
    assert report["error"]["code"] == "SKILL_MISMATCH"
