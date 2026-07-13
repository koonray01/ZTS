from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .utils import canonical_json, iso_z, parse_time, sanitize_id, sha256_json, utc_now


TERMINAL = {"SUCCEEDED", "DEAD_LETTER", "CANCELLED"}


class LeaseOwnershipError(PermissionError):
    pass


class WorkerJobStore:
    def __init__(self, path: str | Path, max_attempts: int = 3):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_attempts = max_attempts

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _append(
        self,
        *,
        event_type: str,
        job_id: str,
        payload: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        events = self.events()
        previous = events[-1]["event_hash"] if events else "GENESIS"
        body = {
            "schema_version": "0.1.0",
            "sequence": len(events) + 1,
            "event_id": sanitize_id(
                f"WORKER_EVENT_{len(events)+1}_{event_type}_{job_id}"
            ),
            "event_type": event_type,
            "job_id": job_id,
            "payload": payload,
            "created_at": iso_z(now),
            "previous_event_hash": previous,
        }
        event = {**body, "event_hash": sha256_json(body)}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(event) + "\n")
            handle.flush()
        return event

    def project(self) -> dict[str, dict[str, Any]]:
        jobs: dict[str, dict[str, Any]] = {}
        for event in self.events():
            job_id = event["job_id"]
            state = jobs.setdefault(
                job_id,
                {
                    "job_id": job_id,
                    "status": None,
                    "job": None,
                    "attempts": 0,
                    "lease_owner": None,
                    "lease_until": None,
                    "available_at": None,
                    "last_error": None,
                },
            )
            event_type = event["event_type"]
            payload = event["payload"]
            if event_type == "JOB_ENQUEUED":
                state["status"] = "QUEUED"
                state["job"] = payload["job"]
                state["available_at"] = event["created_at"]
            elif event_type == "JOB_LEASED":
                state["status"] = "LEASED"
                state["attempts"] += 1
                state["lease_owner"] = payload["worker_id"]
                state["lease_until"] = payload["lease_until"]
            elif event_type == "JOB_STARTED":
                state["status"] = "RUNNING"
            elif event_type == "JOB_HEARTBEAT":
                state["lease_until"] = payload["lease_until"]
            elif event_type in {"JOB_RETRY_WAIT", "LEASE_EXPIRED"}:
                state["status"] = "RETRY_WAIT"
                state["lease_owner"] = None
                state["lease_until"] = None
                state["available_at"] = payload["available_at"]
                state["last_error"] = payload.get("error")
            elif event_type == "JOB_SUCCEEDED":
                state["status"] = "SUCCEEDED"
                state["lease_owner"] = None
                state["lease_until"] = None
                state["result_id"] = payload["result_id"]
            elif event_type == "JOB_DEAD_LETTER":
                state["status"] = "DEAD_LETTER"
                state["lease_owner"] = None
                state["lease_until"] = None
                state["last_error"] = payload["error"]
            elif event_type == "JOB_CANCELLED":
                state["status"] = "CANCELLED"
                state["lease_owner"] = None
                state["lease_until"] = None
        return jobs

    def enqueue(self, job: dict[str, Any], *, now: datetime | None = None) -> bool:
        states = self.project()
        if job["job_id"] in states:
            return False
        self._append(
            event_type="JOB_ENQUEUED",
            job_id=job["job_id"],
            payload={"job": job},
            now=now or utc_now(),
        )
        return True

    def recover_expired(self, *, now: datetime | None = None) -> list[str]:
        current = now or utc_now()
        recovered = []
        for job_id, state in self.project().items():
            if state["status"] not in {"LEASED", "RUNNING"}:
                continue
            if state["lease_until"] and parse_time(state["lease_until"]) <= current:
                available = current + timedelta(seconds=1)
                self._append(
                    event_type="LEASE_EXPIRED",
                    job_id=job_id,
                    payload={
                        "available_at": iso_z(available),
                        "error": "Lease expired before completion.",
                    },
                    now=current,
                )
                recovered.append(job_id)
        return recovered

    def claim(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 60,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        current = now or utc_now()
        self.recover_expired(now=current)
        candidates = []
        for state in self.project().values():
            if state["status"] not in {"QUEUED", "RETRY_WAIT"}:
                continue
            available_at = parse_time(state["available_at"])
            if available_at <= current and state["attempts"] < self.max_attempts:
                candidates.append(state)
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (
                {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}.get(
                    item["job"]["priority"], 9
                ),
                item["available_at"],
                item["job_id"],
            )
        )
        selected = candidates[0]
        lease_until = current + timedelta(seconds=lease_seconds)
        self._append(
            event_type="JOB_LEASED",
            job_id=selected["job_id"],
            payload={
                "worker_id": worker_id,
                "lease_until": iso_z(lease_until),
            },
            now=current,
        )
        return self.project()[selected["job_id"]]

    def _assert_owner(self, job_id: str, worker_id: str) -> dict[str, Any]:
        state = self.project()[job_id]
        if state["lease_owner"] != worker_id or state["status"] not in {"LEASED", "RUNNING"}:
            raise LeaseOwnershipError(f"{worker_id} does not own active lease for {job_id}")
        return state

    def start(self, job_id: str, worker_id: str, *, now: datetime | None = None) -> None:
        self._assert_owner(job_id, worker_id)
        self._append(
            event_type="JOB_STARTED",
            job_id=job_id,
            payload={"worker_id": worker_id},
            now=now or utc_now(),
        )

    def heartbeat(
        self,
        job_id: str,
        worker_id: str,
        *,
        extend_seconds: int = 60,
        now: datetime | None = None,
    ) -> None:
        current = now or utc_now()
        self._assert_owner(job_id, worker_id)
        self._append(
            event_type="JOB_HEARTBEAT",
            job_id=job_id,
            payload={
                "worker_id": worker_id,
                "lease_until": iso_z(current + timedelta(seconds=extend_seconds)),
            },
            now=current,
        )

    def succeed(
        self,
        job_id: str,
        worker_id: str,
        result_id: str,
        *,
        now: datetime | None = None,
    ) -> None:
        self._assert_owner(job_id, worker_id)
        self._append(
            event_type="JOB_SUCCEEDED",
            job_id=job_id,
            payload={"result_id": result_id},
            now=now or utc_now(),
        )

    def fail(
        self,
        job_id: str,
        worker_id: str,
        *,
        error: dict[str, Any],
        retryable: bool,
        retry_delay_seconds: int = 5,
        now: datetime | None = None,
    ) -> str:
        current = now or utc_now()
        state = self._assert_owner(job_id, worker_id)
        if retryable and state["attempts"] < self.max_attempts:
            self._append(
                event_type="JOB_RETRY_WAIT",
                job_id=job_id,
                payload={
                    "available_at": iso_z(
                        current + timedelta(seconds=retry_delay_seconds)
                    ),
                    "error": error,
                },
                now=current,
            )
            return "RETRY_WAIT"
        self._append(
            event_type="JOB_DEAD_LETTER",
            job_id=job_id,
            payload={"error": error},
            now=current,
        )
        return "DEAD_LETTER"

    def cancel(self, job_id: str, *, now: datetime | None = None) -> None:
        state = self.project()[job_id]
        if state["status"] in TERMINAL:
            return
        self._append(
            event_type="JOB_CANCELLED",
            job_id=job_id,
            payload={},
            now=now or utc_now(),
        )


def verify_job_store(path: str | Path) -> tuple[bool, list[str]]:
    store = WorkerJobStore(path)
    errors = []
    previous = "GENESIS"
    for index, event in enumerate(store.events(), start=1):
        if event["sequence"] != index:
            errors.append(f"Sequence mismatch at event {index}.")
        if event["previous_event_hash"] != previous:
            errors.append(f"Previous hash mismatch at event {index}.")
        body = {key: value for key, value in event.items() if key != "event_hash"}
        if event["event_hash"] != sha256_json(body):
            errors.append(f"Event hash mismatch at event {index}.")
        previous = event["event_hash"]
    return not errors, errors
