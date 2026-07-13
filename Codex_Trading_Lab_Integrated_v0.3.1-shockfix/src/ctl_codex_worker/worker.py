from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ctl_permission_agent.tool_gateway import ToolGateway

from .audit import AuditJournal
from .context import build_context
from .errors import PermanentWorkerError, WorkerError
from .job_store import WorkerJobStore
from .provider import ProviderError
from .result_store import ResultStore
from .skill_loader import SkillLoader
from .state_registry import StateRegistry
from .tool_session import ToolSession
from .utils import iso_z, sanitize_id, utc_now
from .validation import ContractValidator


class CodexWorker:
    def __init__(
        self,
        *,
        worker_id: str,
        job_store: WorkerJobStore,
        result_store: ResultStore,
        state_registry: StateRegistry,
        skills_root: str | Path,
        schemas_root: str | Path,
        audit_path: str | Path,
        provider_factory: Callable[[dict[str, Any]], Any],
        max_tool_calls: int = 4,
        max_turns: int = 6,
    ):
        self.worker_id = worker_id
        self.job_store = job_store
        self.result_store = result_store
        self.state_registry = state_registry
        self.skill_loader = SkillLoader(skills_root)
        self.validator = ContractValidator(schemas_root)
        self.audit = AuditJournal(audit_path)
        self.provider_factory = provider_factory
        self.max_tool_calls = max_tool_calls
        self.max_turns = max_turns

    def _effective_tools(
        self,
        job: dict[str, Any],
        skill_manifest: dict[str, Any],
    ) -> list[str]:
        return sorted(
            set(job["allowed_tools"])
            & set(skill_manifest["allowed_tools"])
            & set(ToolGateway.ALLOWED_TOOLS)
        )

    def run_once(
        self,
        *,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> dict[str, Any] | None:
        current = now or utc_now()
        claimed = self.job_store.claim(
            worker_id=self.worker_id,
            lease_seconds=lease_seconds,
            now=current,
        )
        if claimed is None:
            return None

        job = claimed["job"]
        existing = self.result_store.by_job(job["job_id"])
        if existing is not None:
            self.job_store.start(job["job_id"], self.worker_id, now=current)
            self.job_store.succeed(
                job["job_id"],
                self.worker_id,
                existing["result_id"],
                now=current,
            )
            return {
                "job_id": job["job_id"],
                "status": "IDEMPOTENT_ALREADY_COMPLETED",
                "result": existing,
            }

        self.job_store.start(job["job_id"], self.worker_id, now=current)
        self.audit.append(
            "WORKER_JOB_STARTED",
            {
                "worker_id": self.worker_id,
                "job_id": job["job_id"],
                "skill_id": job["skill_id"],
            },
            created_at=current,
        )

        try:
            state = self.state_registry.get(job["snapshot_id"])
            skill = self.skill_loader.load(
                job["skill_id"],
                job["skill_version"],
            )
            effective_tools = self._effective_tools(job, skill["manifest"])
            context = build_context(
                job=job,
                skill=skill,
                state=state,
                effective_tools=effective_tools,
                max_tool_calls=self.max_tool_calls,
            )
            gateway = ToolGateway(state)
            tool_session = ToolSession(
                gateway=gateway,
                effective_tools=effective_tools,
                max_tool_calls=self.max_tool_calls,
            )
            provider = self.provider_factory(job)
            conversation: list[dict[str, Any]] = []
            input_tokens = 0
            output_tokens = 0
            final_payload = None

            for turn_index in range(1, self.max_turns + 1):
                turn = provider.next_turn(
                    context=context,
                    conversation=conversation,
                )
                self.validator.provider_turn(turn)
                input_tokens += int(turn["usage"]["input_tokens"])
                output_tokens += int(turn["usage"]["output_tokens"])
                if input_tokens + output_tokens > job["token_budget"]:
                    from .errors import TokenBudgetExceeded
                    raise TokenBudgetExceeded(
                        f"Token budget exceeded during turn {turn_index}."
                    )

                if turn["turn_type"] == "TOOL_CALLS":
                    traces = []
                    for tool_call in turn["tool_calls"]:
                        trace = tool_session.dispatch(tool_call)
                        traces.append(trace)
                        self.audit.append(
                            "WORKER_TOOL_CALL",
                            {
                                "job_id": job["job_id"],
                                "tool_trace_id": trace["tool_trace_id"],
                                "tool_name": trace["tool_name"],
                                "arguments_hash": trace["arguments_hash"],
                                "result_hash": trace["result_hash"],
                            },
                            created_at=current,
                        )
                    conversation.append(
                        {
                            "turn": turn_index,
                            "tool_traces": traces,
                        }
                    )
                    self.job_store.heartbeat(
                        job["job_id"],
                        self.worker_id,
                        extend_seconds=lease_seconds,
                        now=current,
                    )
                    continue

                final_payload = dict(turn["final"])
                final_payload["schema_version"] = "0.1.0"
                final_payload["result_id"] = sanitize_id(
                    f"WORKER_RESULT_{job['job_id']}"
                )
                final_payload["job_id"] = job["job_id"]
                final_payload["job_type"] = job["job_type"]
                final_payload["skill_id"] = job["skill_id"]
                final_payload["skill_version"] = job["skill_version"]
                final_payload["snapshot_id"] = job["snapshot_id"]
                final_payload["status"] = "SUCCEEDED"
                final_payload["tool_trace_ids"] = [
                    item["tool_trace_id"] for item in tool_session.calls
                ]
                final_payload["usage"] = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                }
                final_payload["provider_id"] = provider.provider_id
                final_payload["generated_at"] = iso_z(current)
                final_payload["auto_execution_enabled"] = False
                self.validator.worker_result(
                    final_payload,
                    token_budget=job["token_budget"],
                    part3_decisions=tool_session.part3_decisions,
                )
                break

            if final_payload is None:
                raise PermanentWorkerError(
                    f"Provider did not return FINAL within {self.max_turns} turns."
                )

            inserted, _record = self.result_store.append(
                final_payload,
                now=current,
            )
            if not inserted:
                final_payload = self.result_store.by_job(job["job_id"])
            self.job_store.succeed(
                job["job_id"],
                self.worker_id,
                final_payload["result_id"],
                now=current,
            )
            self.audit.append(
                "WORKER_JOB_SUCCEEDED",
                {
                    "worker_id": self.worker_id,
                    "job_id": job["job_id"],
                    "result_id": final_payload["result_id"],
                    "provider_id": final_payload["provider_id"],
                    "total_tokens": final_payload["usage"]["total_tokens"],
                },
                created_at=current,
            )
            return {
                "job_id": job["job_id"],
                "status": "SUCCEEDED",
                "result": final_payload,
                "effective_tools": effective_tools,
            }

        except ProviderError as exc:
            error = {
                "code": "PROVIDER_ERROR",
                "message": str(exc),
                "retryable": exc.retryable,
            }
            final_state = self.job_store.fail(
                job["job_id"],
                self.worker_id,
                error=error,
                retryable=exc.retryable,
                now=current,
            )
        except WorkerError as exc:
            error = {
                "code": getattr(exc, "code", "WORKER_ERROR"),
                "message": str(exc),
                "retryable": getattr(exc, "retryable", False),
            }
            final_state = self.job_store.fail(
                job["job_id"],
                self.worker_id,
                error=error,
                retryable=error["retryable"],
                now=current,
            )
        except Exception as exc:
            error = {
                "code": "UNEXPECTED_WORKER_ERROR",
                "message": str(exc),
                "retryable": False,
            }
            final_state = self.job_store.fail(
                job["job_id"],
                self.worker_id,
                error=error,
                retryable=False,
                now=current,
            )

        self.audit.append(
            "WORKER_JOB_FAILED",
            {
                "worker_id": self.worker_id,
                "job_id": job["job_id"],
                "final_state": final_state,
                "error": error,
            },
            created_at=current,
        )
        return {
            "job_id": job["job_id"],
            "status": final_state,
            "error": error,
        }
