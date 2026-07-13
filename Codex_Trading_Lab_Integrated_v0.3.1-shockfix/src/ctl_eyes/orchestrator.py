from __future__ import annotations

from typing import Any

from .base import blocked_output
from .basic_structure import analyze_basic_structure
from .candle_features import analyze_candle_features
from .context import contexts_from_snapshot
from .price_action import analyze_price_action
from .range_state import analyze_range_state
from .swings import analyze_swings
from .trend import analyze_trend
from .volatility import analyze_volatility

SENSORS = (
    ("candle_features", "FEATURE", analyze_candle_features),
    ("confirmed_swings", "STRUCTURE", analyze_swings),
    ("basic_structure", "STRUCTURE", analyze_basic_structure),
    ("trend_state", "TREND", analyze_trend),
    ("range_state", "RANGE", analyze_range_state),
    ("volatility_shock", "VOLATILITY", analyze_volatility),
    ("basic_price_action", "PRICE_ACTION", analyze_price_action),
)


def run_basic_eyes(
    snapshot: dict[str, Any],
    *,
    timeframes: list[str] | None = None,
) -> dict[str, Any]:
    contexts = contexts_from_snapshot(snapshot)
    selected = set(timeframes or [context.timeframe for context in contexts])
    freshness = snapshot.get("freshness", {}).get("status")
    qc_decision = snapshot.get("qc", {}).get("decision")
    blocked_reason: tuple[str, str] | None = None
    if freshness != "FRESH":
        blocked_reason = ("SNAPSHOT_NOT_FRESH", f"Snapshot freshness is {freshness!r}.")
    elif qc_decision != "PASS":
        blocked_reason = ("SNAPSHOT_QC_NOT_PASS", f"Snapshot QC decision is {qc_decision!r}.")

    results: list[dict[str, Any]] = []
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

    status_counts: dict[str, int] = {}
    event_counts: dict[str, int] = {}
    for result in results:
        status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1
        for event in result["events"]:
            event_counts[event["event_type"]] = event_counts.get(event["event_type"], 0) + 1

    return {
        "suite_schema_version": "0.1.0",
        "suite": {"name": "basic_eyes", "version": "0.1.0"},
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
        },
        "generated_at": snapshot["capture_time"],
    }
