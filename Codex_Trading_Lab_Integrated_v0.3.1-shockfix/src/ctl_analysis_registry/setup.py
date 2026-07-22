"""Side-aware SINGLE_TARGET setup outcome evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .identity import stable_id


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _base(decision: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "outcome_id": stable_id("MODEL_OUTCOME", decision["decision_id"], decision["labeling_policy_version"], evidence.get("evidence_id")),
        "decision_id": decision["decision_id"], "decision_type": "SETUP",
        "system": decision["system"], "original_policy_version": decision["labeling_policy_version"],
        "evidence_refs": list(evidence.get("evidence_refs", [])),
        "price_quality": evidence.get("price_quality"), "safety": dict(decision.get("safety", {})),
    }


def _touches(geometry: dict[str, Any], bar: dict[str, Any]) -> tuple[bool, bool, bool]:
    side = geometry["side"]
    entry, stop, target = geometry["entry"], geometry["stop"], geometry["scoring_target"]
    if side == "BUY":
        entry_touch = isinstance(bar.get("ask_low"), (int, float)) and bar["ask_low"] <= entry
        target_touch = isinstance(bar.get("bid_high"), (int, float)) and bar["bid_high"] >= target
        stop_touch = isinstance(bar.get("bid_low"), (int, float)) and bar["bid_low"] <= stop
    else:
        entry_touch = isinstance(bar.get("bid_high"), (int, float)) and bar["bid_high"] >= entry
        target_touch = isinstance(bar.get("ask_low"), (int, float)) and bar["ask_low"] <= target
        stop_touch = isinstance(bar.get("ask_high"), (int, float)) and bar["ask_high"] >= stop
    return entry_touch, target_touch, stop_touch


def _evaluate_bars(geometry: dict[str, Any], bars: list[dict[str, Any]]) -> dict[str, Any]:
    entered = False
    entry_bar_id = None
    for bar in bars:
        entry_touch, target_touch, stop_touch = _touches(geometry, bar)
        if not entered:
            if not entry_touch:
                continue
            entered = True
            entry_bar_id = bar.get("bar_id")
        if target_touch and stop_touch:
            return {"classification": "AMBIGUOUS_SAME_BAR", "entry_bar_id": entry_bar_id, "ambiguous_bar_id": bar.get("bar_id")}
        if target_touch:
            return {"classification": "TP_FIRST", "entry_bar_id": entry_bar_id, "outcome_bar_id": bar.get("bar_id")}
        if stop_touch:
            return {"classification": "SL_FIRST", "entry_bar_id": entry_bar_id, "outcome_bar_id": bar.get("bar_id")}
    return {"classification": "UNRESOLVED" if entered else "ENTRY_NOT_TRIGGERED", "entry_bar_id": entry_bar_id}


def _evaluate_ticks(geometry: dict[str, Any], ticks: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not ticks:
        return None
    entered = False
    side = geometry["side"]
    for tick in sorted(ticks, key=lambda item: str(item.get("tick_time") or "")):
        bid, ask = tick.get("bid"), tick.get("ask")
        if not isinstance(bid, (int, float)) or not isinstance(ask, (int, float)):
            continue
        if not entered:
            entered = ask <= geometry["entry"] if side == "BUY" else bid >= geometry["entry"]
            if not entered:
                continue
        if side == "BUY":
            if bid >= geometry["scoring_target"]:
                return {"classification": "TP_FIRST", "tick_time": tick.get("tick_time")}
            if bid <= geometry["stop"]:
                return {"classification": "SL_FIRST", "tick_time": tick.get("tick_time")}
        else:
            if ask <= geometry["scoring_target"]:
                return {"classification": "TP_FIRST", "tick_time": tick.get("tick_time")}
            if ask >= geometry["stop"]:
                return {"classification": "SL_FIRST", "tick_time": tick.get("tick_time")}
    return None


def refine_same_bar(decision: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    geometry = decision.get("setup_geometry") or {}
    m1 = _evaluate_bars(geometry, list(evidence.get("m1_bars", [])))
    if m1["classification"] in {"TP_FIRST", "SL_FIRST"}:
        return m1
    if m1["classification"] == "AMBIGUOUS_SAME_BAR":
        tick_result = _evaluate_ticks(geometry, list(evidence.get("ticks", [])))
        return tick_result or m1
    tick_result = _evaluate_ticks(geometry, list(evidence.get("ticks", [])))
    return tick_result or {"classification": "AMBIGUOUS_SAME_BAR"}


def label_setup(decision: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    result = _base(decision, evidence)
    if evidence.get("price_quality") == "MID_ONLY_PROXY":
        return {**result, "classification": "INVALID_INPUT", "reason_codes": ["MID_ONLY_PROXY"]}
    qc = evidence.get("qc") if isinstance(evidence.get("qc"), dict) else {}
    if qc.get("status") != "PASS":
        return {**result, "classification": "INVALID_INPUT", "reason_codes": list(qc.get("reasons", [])) or ["EVIDENCE_QC_NOT_PASS"]}
    geometry = decision.get("setup_geometry") if isinstance(decision.get("setup_geometry"), dict) else {}
    required = ("side", "entry", "stop", "scoring_target", "expiry_time")
    if any(geometry.get(field) is None for field in required) or geometry.get("side") not in {"BUY", "SELL"}:
        return {**result, "classification": "INVALID_INPUT", "reason_codes": ["SETUP_GEOMETRY_INVALID"]}
    risk = abs(float(geometry["entry"]) - float(geometry["stop"]))
    if risk <= 0:
        return {**result, "classification": "INVALID_INPUT", "reason_codes": ["SETUP_RISK_NON_POSITIVE"]}
    path = _evaluate_bars(geometry, list(evidence.get("bars", [])))
    if path["classification"] == "AMBIGUOUS_SAME_BAR":
        refined = refine_same_bar(decision, evidence)
        if refined["classification"] in {"TP_FIRST", "SL_FIRST"}:
            path = {**path, **refined}
    if path["classification"] == "ENTRY_NOT_TRIGGERED" and evidence.get("bars"):
        last_close = evidence["bars"][-1].get("close_time")
        if isinstance(last_close, str) and _time(last_close) >= _time(str(geometry["expiry_time"])):
            path["classification"] = "EXPIRED_UNTRIGGERED"
    realized_r = None
    if path["classification"] == "TP_FIRST":
        realized_r = abs(float(geometry["scoring_target"]) - float(geometry["entry"])) / risk
    elif path["classification"] == "SL_FIRST":
        realized_r = -1.0
    return {**result, **path, "realized_r": realized_r, "reason_codes": []}
