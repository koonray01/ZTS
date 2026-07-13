from __future__ import annotations

from typing import Any

from ctl_advanced_eyes import run_advanced_eyes
from ctl_eyes import run_basic_eyes

from .entry_engine import build_entry_packet
from .fusion import build_market_packet
from .plan_renderer import render_current_action_plan
from .scenario_engine import build_scenario_packet


def run_decision_core(
    snapshot: dict[str, Any],
    *,
    profile: str = "STANDARD",
) -> dict[str, Any]:
    basic = run_basic_eyes(snapshot)
    advanced = run_advanced_eyes(snapshot)
    market_packet = build_market_packet(snapshot, basic, advanced, profile=profile)
    scenario_packet = build_scenario_packet(market_packet, basic, advanced)
    entry_packet = build_entry_packet(market_packet, scenario_packet)
    action_plan = render_current_action_plan(market_packet, scenario_packet, entry_packet)
    return {
        "run_id": snapshot["run_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "basic_eyes": basic,
        "advanced_eyes": advanced,
        "market_packet": market_packet,
        "scenario_packet": scenario_packet,
        "entry_packet": entry_packet,
        "current_action_plan": action_plan,
        "execution_permission": "NOT_EVALUATED",
    }
