from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ctl_decision_core import diff_decision_state, run_decision_core
from ctl_permission_agent.jobs import build_codex_job
from ctl_permission_agent.journal import AuditJournal, verify_journal
from ctl_permission_agent.part3 import run_part3

from .debounce import EventDebouncer
from .health import evaluate_health
from .queue import PersistentJobQueue
from .session import SessionController
from .utils import atomic_write_json, iso_z, load_json, utc_now


class LiveRuntime:
    def __init__(self, root: str | Path, symbol: str, *, require_live_source: bool = True):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.session = SessionController(self.root / "state" / "session.json", symbol)
        self.queue = PersistentJobQueue(self.root / "jobs" / "queue.jsonl")
        self.audit = AuditJournal(self.root / "audit" / "runtime.jsonl")
        self.debouncer = EventDebouncer(self.root / "state" / "debounce.json", debounce_seconds=60)
        self.previous_state = load_json(self.root / "state" / "previous_decision_state.json")
        self.pipeline_errors = 0
        self.require_live_source = require_live_source

    def start(self, *, now: datetime | None = None) -> dict[str, Any]:
        if self.session.state["state"] == "CREATED":
            self.session.transition("STARTING", now=now)
        # A session is not eligible for new entries until it has processed one
        # healthy snapshot.  This prevents a newly started runtime from being
        # ACTIVE solely because the process launched successfully.
        self.audit.append("SESSION_STARTED", {"session_id": self.session.state["session_id"], "state": self.session.state["state"]}, created_at=now)
        return self.session.state

    def pause(self, *, now: datetime | None = None) -> dict[str, Any]:
        self.session.transition("PAUSED", now=now)
        self.audit.append("SESSION_PAUSED", {"session_id": self.session.state["session_id"]}, created_at=now)
        return self.session.state

    def resume(self, *, now: datetime | None = None) -> dict[str, Any]:
        self.session.transition("ACTIVE", now=now)
        self.audit.append("SESSION_RESUMED", {"session_id": self.session.state["session_id"]}, created_at=now)
        return self.session.state

    def emergency_lock(self, code: str, *, now: datetime | None = None) -> dict[str, Any]:
        self.session.add_lock(code, critical=True, now=now)
        self.audit.append("EMERGENCY_LOCK", {"code": code}, created_at=now)
        return self.session.state

    def unlock(self, code: str, *, now: datetime | None = None) -> dict[str, Any]:
        self.session.clear_lock(code, now=now)
        if self.session.state["state"] == "LOCKED" and not self.session.state["active_locks"]:
            self.session.transition("ACTIVE", now=now)
        self.audit.append("LOCK_CLEARED", {"code": code}, created_at=now)
        return self.session.state

    def stop(self, *, now: datetime | None = None) -> dict[str, Any]:
        if self.session.state["state"] != "STOPPED":
            self.session.transition("STOPPED", now=now)
        self.audit.append("SESSION_STOPPED", {"session_id": self.session.state["session_id"]}, created_at=now)
        return self.session.state

    def process_snapshot(self, snapshot: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        current_time = now or utc_now()
        if self.session.state["state"] == "STOPPED":
            raise RuntimeError("Cannot process snapshots after session stop.")

        try:
            decision = run_decision_core(snapshot)
            watcher = diff_decision_state(
                self.previous_state,
                decision,
                seen_event_keys=self.debouncer.seen_keys(),
            )
            accepted_events = []
            for event in watcher["significant_events"]:
                if self.debouncer.accept(event["event_key"], current_time):
                    accepted_events.append(event)

            jobs = []
            if accepted_events:
                job = build_codex_job(
                    snapshot_id=snapshot["snapshot_id"],
                    event_types=[item["event_type"] for item in accepted_events],
                    input_refs=[
                        decision["market_packet"]["market_packet_id"],
                        decision["scenario_packet"]["scenario_packet_id"],
                        decision["entry_packet"]["entry_packet_id"],
                    ],
                    now=current_time,
                )
                inserted, _ = self.queue.enqueue(job)
                if inserted:
                    jobs.append(job)
                    self.audit.append("CODEX_JOB_ENQUEUED", job, created_at=current_time)

            queue_ok, _ = self.queue.verify()
            audit_ok, _ = verify_journal(self.audit.path)
            health = evaluate_health(
                snapshot,
                pipeline_errors=self.pipeline_errors,
                queue_ok=queue_ok,
                audit_ok=audit_ok,
                require_live_source=self.require_live_source,
            )
            self.session.state["health"] = health
            if health["status"] == "CRITICAL":
                for issue in health["issues"]:
                    self.session.add_lock(issue, critical=True, now=current_time)
            elif self.session.state["state"] == "STARTING":
                self.session.transition("ACTIVE", now=current_time)

            self.session.record_snapshot(snapshot["snapshot_id"], now=current_time)
            self.previous_state = {
                "market_packet": decision["market_packet"],
                "scenario_packet": decision["scenario_packet"],
                "entry_packet": decision["entry_packet"],
            }
            atomic_write_json(
                self.root / "state" / "previous_decision_state.json",
                self.previous_state,
            )
            atomic_write_json(
                self.root / "outputs" / snapshot["snapshot_id"] / "decision_state.json",
                decision,
            )
            self.audit.append(
                "SNAPSHOT_PROCESSED",
                {
                    "snapshot_id": snapshot["snapshot_id"],
                    "accepted_event_count": len(accepted_events),
                    "job_count": len(jobs),
                },
                created_at=current_time,
            )
            return {
                "session": self.session.state,
                "decision_state": decision,
                "watcher": {
                    **watcher,
                    "accepted_significant_events": accepted_events,
                },
                "jobs_created": jobs,
                "health": health,
            }
        except Exception as exc:
            self.pipeline_errors += 1
            self.audit.append(
                "PIPELINE_ERROR",
                {"error_type": type(exc).__name__, "message": str(exc)},
                created_at=current_time,
            )
            if self.pipeline_errors >= 3:
                self.emergency_lock("PIPELINE_ERROR_THRESHOLD", now=current_time)
            raise

    def run_part3_if_allowed(
        self,
        *,
        snapshot: dict[str, Any],
        decision_state: dict[str, Any],
        candidate_id: str,
        account: dict[str, Any],
        dependency_state: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not self.session.state["new_entries_allowed"]:
            return {
                "decision": "WAIT",
                "reason": f"Session state {self.session.state['state']} blocks new entries.",
                "execution_scope": "MANUAL_ONLY",
            }
        decision = run_part3(
            snapshot=snapshot,
            market_packet=decision_state["market_packet"],
            scenario_packet=decision_state["scenario_packet"],
            entry_packet=decision_state["entry_packet"],
            candidate_id=candidate_id,
            account=account,
            dependency_state=dependency_state,
            now=now,
        )
        self.audit.append("PART3_DECISION", decision, created_at=now)
        return decision
