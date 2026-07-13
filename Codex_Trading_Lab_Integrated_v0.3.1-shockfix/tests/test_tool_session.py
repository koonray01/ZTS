from __future__ import annotations

import pytest

from ctl_codex_worker.errors import (
    DisallowedTool,
    ToolBudgetExceeded,
    ToolLoopDetected,
)
from ctl_codex_worker.tool_session import ToolSession
from ctl_permission_agent.tool_gateway import ToolGateway


def test_allowed_tool_dispatches(state):
    session = ToolSession(
        gateway=ToolGateway(state),
        effective_tools=["get_current_state"],
        max_tool_calls=2,
    )
    trace = session.dispatch(
        {
            "tool_call_id": "CALL-1",
            "tool_name": "get_current_state",
            "arguments": {},
        }
    )
    assert trace["tool_name"] == "get_current_state"


def test_disallowed_tool_blocked(state):
    session = ToolSession(
        gateway=ToolGateway(state),
        effective_tools=["get_current_state"],
        max_tool_calls=2,
    )
    with pytest.raises(DisallowedTool):
        session.dispatch(
            {
                "tool_call_id": "CALL-1",
                "tool_name": "run_part3",
                "arguments": {
                    "candidate_id": "X",
                    "account": {},
                    "dependency_state": {},
                },
            }
        )


def test_duplicate_call_loop_blocked(state):
    session = ToolSession(
        gateway=ToolGateway(state),
        effective_tools=["get_current_state"],
        max_tool_calls=3,
    )
    call = {
        "tool_call_id": "CALL-1",
        "tool_name": "get_current_state",
        "arguments": {},
    }
    session.dispatch(call)
    with pytest.raises(ToolLoopDetected):
        session.dispatch({**call, "tool_call_id": "CALL-2"})


def test_tool_budget_enforced(state):
    session = ToolSession(
        gateway=ToolGateway(state),
        effective_tools=["get_current_state", "list_entry_candidates"],
        max_tool_calls=1,
    )
    session.dispatch(
        {
            "tool_call_id": "CALL-1",
            "tool_name": "get_current_state",
            "arguments": {},
        }
    )
    with pytest.raises(ToolBudgetExceeded):
        session.dispatch(
            {
                "tool_call_id": "CALL-2",
                "tool_name": "list_entry_candidates",
                "arguments": {},
            }
        )
