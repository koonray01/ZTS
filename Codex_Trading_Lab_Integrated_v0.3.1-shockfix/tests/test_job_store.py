from __future__ import annotations

from datetime import timedelta

import pytest

from ctl_codex_worker.job_store import LeaseOwnershipError, verify_job_store


def test_enqueue_is_idempotent(stores, market_job, now):
    assert stores["jobs"].enqueue(market_job, now=now) is True
    assert stores["jobs"].enqueue(market_job, now=now) is False
    assert len(stores["jobs"].project()) == 1


def test_claim_priority_and_lease(stores, market_job, now):
    stores["jobs"].enqueue(market_job, now=now)
    state = stores["jobs"].claim(worker_id="W1", now=now)
    assert state["status"] == "LEASED"
    assert state["lease_owner"] == "W1"
    assert state["attempts"] == 1


def test_wrong_owner_cannot_start(stores, market_job, now):
    stores["jobs"].enqueue(market_job, now=now)
    stores["jobs"].claim(worker_id="W1", now=now)
    with pytest.raises(LeaseOwnershipError):
        stores["jobs"].start(market_job["job_id"], "W2", now=now)


def test_expired_lease_recovers(stores, market_job, now):
    stores["jobs"].enqueue(market_job, now=now)
    stores["jobs"].claim(worker_id="W1", lease_seconds=1, now=now)
    recovered = stores["jobs"].recover_expired(now=now + timedelta(seconds=2))
    assert market_job["job_id"] in recovered
    assert stores["jobs"].project()[market_job["job_id"]]["status"] == "RETRY_WAIT"


def test_completed_job_not_claimed_again(stores, market_job, now):
    stores["jobs"].enqueue(market_job, now=now)
    stores["jobs"].claim(worker_id="W1", now=now)
    stores["jobs"].start(market_job["job_id"], "W1", now=now)
    stores["jobs"].succeed(market_job["job_id"], "W1", "RESULT-1", now=now)
    assert stores["jobs"].claim(worker_id="W2", now=now) is None


def test_store_integrity(stores, market_job, now):
    stores["jobs"].enqueue(market_job, now=now)
    stores["jobs"].claim(worker_id="W1", now=now)
    assert verify_job_store(stores["jobs"].path) == (True, [])
