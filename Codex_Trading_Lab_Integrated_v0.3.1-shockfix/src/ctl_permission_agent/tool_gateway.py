from __future__ import annotations

from typing import Any, Callable

from .jobs import build_codex_job
from .part3 import run_part3
from .proposal import build_manual_execution_proposal


class ToolNotAllowed(PermissionError):
    pass


class ToolGateway:
    ALLOWED_TOOLS = {
        "get_current_state",
        "list_entry_candidates",
        "run_part3",
        "explain_decision",
        "build_manual_execution_proposal",
        "inspect_evidence_refs",
        "build_codex_job",
    }

    def __init__(self, state: dict[str, Any]):
        self.state = state
        self.decisions: dict[str, dict[str, Any]] = {}

    def call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if tool_name not in self.ALLOWED_TOOLS:
            raise ToolNotAllowed(f"Tool is not allowlisted: {tool_name}")
        return getattr(self, f"_tool_{tool_name}")(**arguments)

    def _tool_get_current_state(self) -> dict[str, Any]:
        return {
            "market_packet": self.state["market_packet"],
            "scenario_packet": self.state["scenario_packet"],
            "entry_summary": [
                {
                    "candidate_id": item["candidate_id"],
                    "entry_type": item["entry_type"],
                    "side": item["side"],
                    "status": item["status"],
                    "limit_eligibility": item["limit_eligibility"],
                }
                for item in self.state["entry_packet"]["candidates"]
            ],
        }

    def _tool_list_entry_candidates(self) -> list[dict[str, Any]]:
        return self.state["entry_packet"]["candidates"]

    def _tool_run_part3(
        self,
        candidate_id: str,
        account: dict[str, Any],
        dependency_state: dict[str, Any],
        risk_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        decision = run_part3(
            snapshot=self.state["snapshot"],
            market_packet=self.state["market_packet"],
            scenario_packet=self.state["scenario_packet"],
            entry_packet=self.state["entry_packet"],
            candidate_id=candidate_id,
            account=account,
            dependency_state=dependency_state,
            risk_policy=risk_policy,
            prior_decision_ids=set(self.decisions),
        )
        self.decisions[decision["decision_id"]] = decision
        return decision

    def _tool_explain_decision(self, decision_id: str) -> dict[str, Any]:
        decision = self.decisions[decision_id]
        return {
            "decision_id": decision_id,
            "decision": decision["decision"],
            "failed_gates": decision["failed_gates"],
            "pending_gates": decision["pending_gates"],
            "what_to_wait_for": decision["what_to_wait_for"],
            "prohibited_actions": decision["prohibited_actions"],
            "gate_details": decision["gates"],
        }

    def _tool_build_manual_execution_proposal(self, decision_id: str) -> dict[str, Any]:
        return build_manual_execution_proposal(
            decision=self.decisions[decision_id],
            entry_packet=self.state["entry_packet"],
        )

    def _tool_inspect_evidence_refs(self, evidence_refs: list[str]) -> dict[str, Any]:
        known = set(self.state["market_packet"]["evidence_refs"])
        return {
            "requested": evidence_refs,
            "known": [item for item in evidence_refs if item in known],
            "unresolved": [item for item in evidence_refs if item not in known],
            "raw_evidence_mutation_allowed": False,
        }

    def _tool_build_codex_job(self, event_types: list[str], input_refs: list[str]) -> dict[str, Any]:
        return build_codex_job(
            snapshot_id=self.state["snapshot"]["snapshot_id"],
            event_types=event_types,
            input_refs=input_refs,
        )
