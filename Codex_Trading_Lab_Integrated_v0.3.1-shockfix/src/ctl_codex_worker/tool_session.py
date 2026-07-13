from __future__ import annotations

import json
from typing import Any

from .errors import DisallowedTool, ToolBudgetExceeded, ToolLoopDetected
from .utils import sanitize_id, sha256_json


TOOL_ARGUMENT_RULES = {
    "get_current_state": set(),
    "list_entry_candidates": set(),
    "run_part3": {"candidate_id", "account", "dependency_state", "risk_policy"},
    "explain_decision": {"decision_id"},
    "build_manual_execution_proposal": {"decision_id"},
    "inspect_evidence_refs": {"evidence_refs"},
    "build_codex_job": {"event_types", "input_refs"},
}


def _compact_tool_result(tool_name: str, result: Any) -> Any:
    """Keep model-facing tool payloads compact without changing deterministic truth."""
    if tool_name == "get_current_state" and isinstance(result, dict):
        market = result.get("market_packet", {})
        scenarios = result.get("scenario_packet", {})
        return {
            "market_packet": {
                "market_packet_id": market.get("market_packet_id"),
                "snapshot_id": market.get("snapshot_id"),
                "symbol": market.get("symbol"),
                "market_state": market.get("market_state", []),
                "location": market.get("location", {}),
                "risk_flags": market.get("risk_flags", []),
                "conflicts": market.get("conflicts", []),
                "unknowns": market.get("unknowns", []),
                "permission_state": market.get("permission_state"),
                "evidence_refs": market.get("evidence_refs", [])[:20],
            },
            "scenario_packet": {
                "scenario_packet_id": scenarios.get("scenario_packet_id"),
                "ranking_method": scenarios.get("ranking_method"),
                "probability_status": scenarios.get("probability_status"),
                "scenarios": [
                    {
                        "scenario_id": item.get("scenario_id"),
                        "rank": item.get("rank"),
                        "label": item.get("label"),
                        "direction": item.get("direction"),
                        "status": item.get("status"),
                        "what_to_wait_for": item.get("what_to_wait_for", []),
                        "prohibited_actions": item.get("prohibited_actions", []),
                        "evidence_refs": item.get("evidence_refs", [])[:10],
                    }
                    for item in scenarios.get("scenarios", [])
                ],
            },
            "entry_summary": result.get("entry_summary", []),
        }

    if tool_name == "list_entry_candidates" and isinstance(result, list):
        return [
            {
                "candidate_id": item.get("candidate_id"),
                "scenario_id": item.get("scenario_id"),
                "entry_type": item.get("entry_type"),
                "side": item.get("side"),
                "status": item.get("status"),
                "entry_range": item.get("entry_range"),
                "stop": item.get("stop"),
                "targets": item.get("targets"),
                "rr": item.get("rr"),
                "missing_conditions": item.get("missing_conditions", []),
                "limit_eligibility": item.get("limit_eligibility"),
                "permission_state": item.get("permission_state"),
                "evidence_refs": item.get("evidence_refs", [])[:12],
            }
            for item in result
        ]

    return result


class ToolSession:
    def __init__(
        self,
        *,
        gateway: Any,
        effective_tools: list[str],
        max_tool_calls: int,
        max_result_chars: int = 50000,
    ):
        self.gateway = gateway
        self.effective_tools = set(effective_tools)
        self.max_tool_calls = max_tool_calls
        self.max_result_chars = max_result_chars
        self.calls: list[dict[str, Any]] = []
        self._signatures: set[str] = set()
        self.part3_decisions: list[dict[str, Any]] = []

    def dispatch(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        if len(self.calls) >= self.max_tool_calls:
            raise ToolBudgetExceeded("Maximum tool-call budget reached.")

        name = tool_call["tool_name"]
        arguments = tool_call["arguments"]
        if name not in self.effective_tools:
            raise DisallowedTool(f"Tool is outside effective allowlist: {name}")
        if name not in TOOL_ARGUMENT_RULES:
            raise DisallowedTool(f"No argument contract registered for tool: {name}")

        allowed_keys = TOOL_ARGUMENT_RULES[name]
        supplied = set(arguments)
        required = {
            "run_part3": {"candidate_id", "account", "dependency_state"},
            "explain_decision": {"decision_id"},
            "build_manual_execution_proposal": {"decision_id"},
            "inspect_evidence_refs": {"evidence_refs"},
            "build_codex_job": {"event_types", "input_refs"},
        }.get(name, set())

        if supplied - allowed_keys:
            raise DisallowedTool(
                f"Unexpected tool arguments for {name}: "
                f"{sorted(supplied - allowed_keys)}"
            )
        if required - supplied:
            raise DisallowedTool(
                f"Missing tool arguments for {name}: "
                f"{sorted(required - supplied)}"
            )

        signature = sha256_json({"tool_name": name, "arguments": arguments})
        if signature in self._signatures:
            raise ToolLoopDetected(f"Duplicate tool call detected: {name}")
        self._signatures.add(signature)

        raw_result = self.gateway.call(name, arguments)
        result = _compact_tool_result(name, raw_result)
        if len(json.dumps(result, ensure_ascii=False, separators=(",", ":"))) > self.max_result_chars:
            raise ToolBudgetExceeded("Compacted tool result exceeds maximum result size.")

        trace = {
            "tool_trace_id": sanitize_id(
                f"TOOL_TRACE_{tool_call['tool_call_id']}_{len(self.calls)+1}"
            ),
            "tool_call_id": tool_call["tool_call_id"],
            "tool_name": name,
            "arguments_hash": sha256_json(arguments),
            "raw_result_hash": sha256_json(raw_result),
            "result_hash": sha256_json(result),
            "result": result,
        }
        self.calls.append(trace)
        if name == "run_part3":
            self.part3_decisions.append(raw_result)
        return trace
