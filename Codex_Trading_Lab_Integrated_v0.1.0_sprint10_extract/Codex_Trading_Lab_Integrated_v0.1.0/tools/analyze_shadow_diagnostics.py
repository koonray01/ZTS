from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REASON_PRIORITY = [
    "SNAPSHOT_QC_BLOCK",
    "STALE_DATA_BLOCK",
    "SHOCK_BLOCK",
    "NO_OPPORTUNITY",
    "SCENARIO_NOT_READY",
    "NO_VALID_LOCATION",
    "NO_ACTIVE_ZONE",
    "TRIGGER_PENDING",
    "LIMIT_NOT_ELIGIBLE",
    "RR_BELOW_MINIMUM",
    "REQUIRED_INPUT_UNKNOWN",
    "OTHER_EXPLICIT_REASON",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _claim_value(items: list[dict[str, Any]], name: str) -> Any:
    for item in items:
        if item.get("name") == name:
            return item.get("value")
    return None


def _decision_files(output: Path) -> list[Path]:
    return sorted((output / "evidence" / "normalized").glob("*/*/*/*/decision_state.json"))


def _raw_snapshot(output: Path, run_id: str) -> dict[str, Any] | None:
    matches = list((output / "evidence" / "raw").glob(f"*/*/*/{run_id}/snapshot.json"))
    if not matches:
        return None
    return _load_json(matches[0])


def _reasons_for_snapshot(payload: dict[str, Any]) -> tuple[str, list[str]]:
    market = payload["market_packet"]
    scenarios = payload["scenario_packet"]["scenarios"]
    candidates = payload["entry_packet"]["candidates"]
    reasons: list[str] = []
    if market.get("freshness", {}).get("status") == "STALE":
        reasons.append("STALE_DATA_BLOCK")
    if market.get("freshness", {}).get("status") == "BLOCKED":
        reasons.append("SNAPSHOT_QC_BLOCK")
    if any(flag.get("severity") == "BLOCK" for flag in market.get("risk_flags", [])):
        reasons.append("SHOCK_BLOCK")
    if not market.get("opportunities", []):
        reasons.append("NO_OPPORTUNITY")
    if candidates:
        for candidate in candidates:
            if candidate.get("limit_eligibility") not in {"NOT_APPLICABLE", "LIMIT_READY", "LIMIT_WATCH"}:
                reasons.append("LIMIT_NOT_ELIGIBLE")
            if candidate.get("trigger", {}).get("status") == "PENDING":
                reasons.append("TRIGGER_PENDING")
    else:
        if any(item.get("status") not in {"ACTIVE", "WATCH"} for item in scenarios):
            reasons.append("SCENARIO_NOT_READY")
    unique = list(dict.fromkeys(reasons or ["OTHER_EXPLICIT_REASON"]))
    primary = next((reason for reason in REASON_PRIORITY if reason in unique), unique[0])
    secondary = [reason for reason in unique if reason != primary]
    return primary, secondary


def analyze(output: Path) -> dict[str, Any]:
    files = _decision_files(output)
    shock_by_timeframe: Counter[str] = Counter()
    volatility_by_timeframe: dict[str, Counter[str]] = defaultdict(Counter)
    shock_trigger_reason: Counter[str] = Counter()
    sensor_block_reasons: Counter[str] = Counter()
    primary_suppression: Counter[str] = Counter()
    secondary_suppression: Counter[str] = Counter()
    shock_input_values: dict[str, list[dict[str, Any]]] = defaultdict(list)
    shock_state_transitions: list[dict[str, Any]] = []
    previous_volatility: dict[str, str] = {}
    started = 0
    cleared = 0
    active_snapshots = 0
    longest_streak = 0
    current_streak = 0
    funnel = Counter()

    for path in files:
        wrapper = _load_json(path)
        payload = wrapper["payload"]
        market = payload["market_packet"]
        raw = _raw_snapshot(output, wrapper["run_id"])
        primary, secondary = _reasons_for_snapshot(payload)
        primary_suppression[primary] += 1
        secondary_suppression.update(secondary)

        states = market["market_state"]
        has_shock = any(state.get("volatility") == "SHOCK" for state in states)
        if has_shock:
            active_snapshots += 1
            current_streak += 1
            longest_streak = max(longest_streak, current_streak)
        else:
            current_streak = 0
        funnel["snapshots"] += 1
        if market.get("location", {}).get("status") not in {None, "UNKNOWN", "UNAVAILABLE"}:
            funnel["valid_locations"] += 1
        funnel["active_zones"] += len(market.get("active_zones", []))
        funnel["opportunities"] += len(market.get("opportunities", []))
        funnel["scenarios"] += len(payload["scenario_packet"]["scenarios"])
        funnel["ready_scenarios"] += sum(1 for item in payload["scenario_packet"]["scenarios"] if item.get("status") in {"ACTIVE", "WATCH"})
        funnel["entry_candidates"] += len(payload["entry_packet"]["candidates"])

        for state in states:
            tf = state["timeframe"]
            vol = state.get("volatility", "UNKNOWN")
            volatility_by_timeframe[tf][vol] += 1
            if previous_volatility.get(tf) != vol:
                shock_state_transitions.append({"snapshot_id": payload["snapshot_id"], "timeframe": tf, "from": previous_volatility.get(tf), "to": vol})
                if previous_volatility.get(tf) != "SHOCK" and vol == "SHOCK":
                    started += 1
                if previous_volatility.get(tf) == "SHOCK" and vol != "SHOCK":
                    cleared += 1
            previous_volatility[tf] = vol
            if vol == "SHOCK":
                shock_by_timeframe[tf] += 1

        for result in payload["basic_eyes"]["results"]:
            if result["sensor"]["name"] != "volatility_shock":
                continue
            tf = result["timeframe"]
            for unknown in result.get("unknowns", []):
                sensor_block_reasons[unknown["code"]] += 1
            derived = result.get("derived", [])
            facts = result.get("facts", [])
            values = {
                "timeframe": tf,
                "volatility_state": _claim_value(derived, "volatility_state"),
                "true_range_ratio": _claim_value(derived, "true_range_ratio"),
                "body_dominance_ratio": _claim_value(derived, "body_dominance_ratio"),
                "latest_true_range": _claim_value(facts, "latest_true_range"),
                "rolling_median_true_range": _claim_value(facts, "rolling_median_true_range"),
            }
            if any(value is not None for key, value in values.items() if key != "timeframe"):
                shock_input_values[tf].append(values)
            for event in result.get("events", []):
                if event.get("event_type") == "SHOCK":
                    shock_trigger_reason[f"{tf}:{event.get('direction')}"] += 1

    return {
        "snapshots_analyzed": len(files),
        "shock_active_snapshots": active_snapshots,
        "shock_started_count": started,
        "shock_cleared_count": cleared,
        "longest_shock_duration_snapshots": longest_streak,
        "shock_by_timeframe": {key: dict(value) for key, value in sorted(volatility_by_timeframe.items())},
        "shock_trigger_reason": dict(shock_trigger_reason),
        "shock_threshold_values": {
            "true_range_ratio_shock": ">= 3.0",
            "true_range_ratio_body_shock": ">= 2.0 and body_dominance_ratio >= 0.70",
            "elevated": ">= 1.8",
        },
        "shock_input_values_available": {key: len(value) for key, value in shock_input_values.items()},
        "shock_input_value_samples": {key: value[:3] for key, value in shock_input_values.items()},
        "shock_state_transitions": shock_state_transitions[:50],
        "sensor_block_reasons": dict(sensor_block_reasons),
        "primary_suppression_reason": dict(primary_suppression),
        "secondary_suppression_reasons": dict(secondary_suppression),
        "funnel": dict(funnel),
        "audit_decision": (
            "SHOCK_INPUT_MAPPING_ERROR"
            if active_snapshots == 0 and sensor_block_reasons
            else "SHOCK_BEHAVIOR_CONFIRMED_REAL"
            if active_snapshots > 0
            else "SHOCK_AUDIT_INCONCLUSIVE"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Sprint 11 shadow diagnostics and shock behavior.")
    parser.add_argument("--output", required=True, help="Forward shadow output directory.")
    parser.add_argument("--report-json", required=True)
    args = parser.parse_args()
    result = analyze(Path(args.output))
    report = Path(args.report_json)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"audit_decision": result["audit_decision"], "snapshots": result["snapshots_analyzed"], "report": str(report)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
