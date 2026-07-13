from __future__ import annotations

from typing import Any

from ctl_eyes.base import blocked_output
from ctl_eyes.context import contexts_from_snapshot

from .dealing_range import analyze_dealing_range
from .fvg import analyze_fair_value_gaps
from .liquidity import analyze_liquidity_map
from .order_blocks import analyze_order_block_candidates
from .smc_structure import analyze_smc_structure
from .supply_demand import analyze_supply_demand
from .support_resistance import analyze_support_resistance
from .zone_primitives import analyze_zone_primitives

SENSORS = (
    ("zone_primitives", "ZONE", analyze_zone_primitives),
    ("support_resistance", "ZONE", analyze_support_resistance),
    ("supply_demand_candidates", "ZONE", analyze_supply_demand),
    ("liquidity_map", "LIQUIDITY", analyze_liquidity_map),
    ("fair_value_gap", "PRICE_ACTION", analyze_fair_value_gaps),
    ("smc_structure_interpretation", "STRUCTURE", analyze_smc_structure),
    ("order_block_candidates", "ZONE", analyze_order_block_candidates),
    ("dealing_range", "CONTEXT", analyze_dealing_range),
)


def run_advanced_eyes(
    snapshot: dict[str, Any],
    *,
    timeframes: list[str] | None = None,
) -> dict[str, Any]:
    contexts = contexts_from_snapshot(snapshot)
    selected = set(timeframes or [context.timeframe for context in contexts])
    freshness = snapshot.get("freshness", {}).get("status")
    qc_decision = snapshot.get("qc", {}).get("decision")
    blocked_reason = None
    if freshness != "FRESH":
        blocked_reason = ("SNAPSHOT_NOT_FRESH", f"Snapshot freshness is {freshness!r}.")
    elif qc_decision != "PASS":
        blocked_reason = ("SNAPSHOT_QC_NOT_PASS", f"Snapshot QC decision is {qc_decision!r}.")

    results = []
    for context in contexts:
        if context.timeframe not in selected:
            continue
        for sensor_name, category, function in SENSORS:
            if blocked_reason:
                result = blocked_output(
                    context,
                    sensor_name,
                    category,
                    blocked_reason[0],
                    blocked_reason[1],
                )
            else:
                result = function(context)
            results.append(result)

    status_counts = {}
    event_counts = {}
    for result in results:
        status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1
        for event in result["events"]:
            event_counts[event["event_type"]] = event_counts.get(event["event_type"], 0) + 1

    return {
        "suite_schema_version": "0.1.0",
        "suite": {"name": "advanced_eyes", "version": "0.1.0"},
        "run_id": snapshot["run_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "symbol": snapshot["symbol"],
        "source": snapshot["source"],
        "timeframes": sorted(selected),
        "results": results,
        "summary": {
            "sensor_result_count": len(results),
            "status_counts": status_counts,
            "event_counts": event_counts,
            "trade_permission": "NOT_EVALUATED",
            "interpretation_layer": "RESEARCH_DEFINITION_V0_1",
        },
        "generated_at": snapshot["capture_time"],
    }
