"""Deterministic four-tier conditional watch setup generation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .identity import stable_id


STRICTNESS: dict[str, dict[str, float | int]] = {
    "EXPLORATORY": {"min_rr": 0.50, "rank": 0, "required_events": 1},
    "VERY_RELAXED": {"min_rr": 0.75, "rank": 1, "required_events": 2},
    "RELAXED": {"min_rr": 1.00, "rank": 2, "required_events": 3},
    "NORMAL": {"min_rr": 1.50, "rank": 3, "required_events": 4},
}
HORIZONS: dict[str, dict[str, Any]] = {
    "SCALPING": {
        "activation_tf": "M5",
        "context_tfs": ["M15", "H1"],
        "evaluation_horizon": "PT30M",
        "activation_minutes": 30,
        "evaluation_minutes": 30,
    },
    "DAYTRADE": {
        "activation_tf": "M15",
        "context_tfs": ["H1", "H4"],
        "evaluation_horizon": "PT2H",
        "activation_minutes": 120,
        "evaluation_minutes": 120,
    },
}
SIDES = {"SELL": "SELL_CONTINUATION", "BUY": "BUY_REVERSAL"}
GEOMETRY_POLICY_VERSION = "FOUR_TIER_GEOMETRY_V1"


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _bound(zone: dict[str, Any], name: str) -> float:
    aliases = {"lower": ("lower", "lower_bound"), "upper": ("upper", "upper_bound")}
    for key in aliases[name]:
        value = zone.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    raise ValueError(f"zone {zone.get('zone_id')} has no numeric {name} bound")


def _zone_kind(zone: dict[str, Any]) -> str:
    token = str(zone.get("zone_type") or zone.get("side") or "").upper()
    for kind in ("DEMAND", "SUPPORT", "SUPPLY", "RESISTANCE"):
        if kind in token:
            return kind
    return token


def _require_live_safe_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("source") != "LIVE_MT5":
        raise ValueError("setup matrix requires source=LIVE_MT5")
    if snapshot.get("freshness", {}).get("status") != "FRESH":
        raise ValueError("setup matrix requires fresh evidence")
    if snapshot.get("qc", {}).get("decision") != "PASS":
        raise ValueError("setup matrix requires QC PASS")
    terminal = snapshot.get("terminal", {})
    if terminal and terminal.get("connected") is False:
        raise ValueError("setup matrix requires connected MT5")
    if terminal.get("trade_write_enabled") is True:
        raise ValueError("setup matrix requires trade_write_enabled=false")


def _reference_price(snapshot: dict[str, Any]) -> float:
    quote = snapshot.get("quote", {})
    bid, ask = quote.get("bid"), quote.get("ask")
    if not isinstance(bid, (int, float)) or not isinstance(ask, (int, float)):
        raise ValueError("setup matrix requires numeric bid and ask")
    if float(ask) < float(bid):
        raise ValueError("setup matrix ask cannot be below bid")
    return (float(bid) + float(ask)) / 2.0


def _timeframe_rank(activation_tf: str, context_tfs: list[str]) -> dict[str, int]:
    return {activation_tf: 0, **{tf: index + 1 for index, tf in enumerate(context_tfs)}}


def select_zone(
    active_zones: list[dict[str, Any]],
    side: str,
    activation_tf: str,
    context_tfs: list[str],
    reference: float,
) -> dict[str, Any] | None:
    allowed = {"BUY": {"DEMAND", "SUPPORT"}, "SELL": {"SUPPLY", "RESISTANCE"}}[side]
    ranks = _timeframe_rank(activation_tf, context_tfs)
    candidates: list[dict[str, Any]] = []
    for zone in active_zones:
        if zone.get("status", "ACTIVE") != "ACTIVE":
            continue
        if zone.get("timeframe") not in ranks or _zone_kind(zone) not in allowed:
            continue
        try:
            _bound(zone, "lower")
            _bound(zone, "upper")
        except ValueError:
            continue
        candidates.append(zone)
    return min(
        candidates,
        key=lambda zone: (
            ranks[str(zone["timeframe"])],
            abs(((_bound(zone, "lower") + _bound(zone, "upper")) / 2.0) - reference),
            str(zone.get("zone_id")),
        ),
        default=None,
    )


def _opposing_zones(
    active_zones: list[dict[str, Any]],
    side: str,
    entry: float,
) -> list[dict[str, Any]]:
    allowed = {"BUY": {"SUPPLY", "RESISTANCE"}, "SELL": {"DEMAND", "SUPPORT"}}[side]
    rows: list[dict[str, Any]] = []
    for zone in active_zones:
        if zone.get("status", "ACTIVE") != "ACTIVE" or _zone_kind(zone) not in allowed:
            continue
        try:
            midpoint = (_bound(zone, "lower") + _bound(zone, "upper")) / 2.0
        except ValueError:
            continue
        if (side == "BUY" and midpoint > entry) or (side == "SELL" and midpoint < entry):
            rows.append(zone)
    return sorted(
        rows,
        key=lambda zone: (
            abs(((_bound(zone, "lower") + _bound(zone, "upper")) / 2.0) - entry),
            str(zone.get("zone_id")),
        ),
    )


def valid_geometry(
    side: str,
    entry: float,
    stop: float,
    target: float,
    min_rr: float,
) -> bool:
    if side == "BUY" and not stop < entry < target:
        return False
    if side == "SELL" and not target < entry < stop:
        return False
    risk = abs(entry - stop)
    return risk > 0 and abs(target - entry) / risk >= min_rr


def _geometry(
    snapshot: dict[str, Any],
    active_zones: list[dict[str, Any]],
    side: str,
    horizon: dict[str, Any],
    min_rr: float,
) -> dict[str, Any]:
    reference = _reference_price(snapshot)
    zone = select_zone(
        active_zones,
        side,
        str(horizon["activation_tf"]),
        list(horizon["context_tfs"]),
        reference,
    )
    if zone is None:
        return {"scorable": False, "reason": "ENTRY_ZONE_UNAVAILABLE"}
    lower, upper = _bound(zone, "lower"), _bound(zone, "upper")
    entry = (lower + upper) / 2.0
    quote = snapshot["quote"]
    spread = max(float(quote["ask"]) - float(quote["bid"]), 0.0)
    buffer = max(spread, abs(upper - lower) * 0.10, 0.01)
    stop = lower - buffer if side == "BUY" else upper + buffer
    for target_zone in _opposing_zones(active_zones, side, entry):
        target = (_bound(target_zone, "lower") + _bound(target_zone, "upper")) / 2.0
        if valid_geometry(side, entry, stop, target, min_rr):
            return {
                "scorable": True,
                "entry_zone": zone,
                "target_zone": target_zone,
                "entry": entry,
                "stop": stop,
                "target": target,
                "buffer": buffer,
            }
    return {
        "scorable": False,
        "reason": "TARGET_OR_RR_UNAVAILABLE",
        "entry_zone": zone,
        "entry": entry,
        "stop": stop,
        "buffer": buffer,
    }


def _market_context(decision_state: dict[str, Any], activation_tf: str) -> dict[str, str]:
    states = decision_state.get("market_packet", {}).get("market_state", [])
    state = next((row for row in states if row.get("timeframe") == activation_tf), {})
    return {
        "regime": str(state.get("regime") or "UNKNOWN"),
        "volatility": str(state.get("volatility") or "UNKNOWN"),
    }


def _build_claim(
    snapshot: dict[str, Any],
    decision_state: dict[str, Any],
    generation_id: str,
    setup_horizon: str,
    strictness: str,
    side: str,
) -> dict[str, Any]:
    horizon = HORIZONS[setup_horizon]
    policy = STRICTNESS[strictness]
    geometry = _geometry(
        snapshot,
        list(decision_state.get("market_packet", {}).get("active_zones", [])),
        side,
        horizon,
        float(policy["min_rr"]),
    )
    decision_time = _time(str(snapshot["capture_time"]))
    activation_expiry = decision_time + timedelta(minutes=int(horizon["activation_minutes"]))
    outcome_expiry = activation_expiry + timedelta(minutes=int(horizon["evaluation_minutes"]))
    opportunity_id = stable_id(
        "SETUP_OPPORTUNITY",
        generation_id,
        setup_horizon,
        SIDES[side],
    )
    entry = geometry.get("entry")
    stop = geometry.get("stop")
    target = geometry.get("target")
    event_type = "CLOSED_ABOVE" if side == "BUY" else "CLOSED_BELOW"
    condition = {
        "event_type": event_type,
        "timeframe": horizon["activation_tf"],
        "price_field": "MID_CLOSE",
        "level": entry,
    }
    entry_zone = geometry.get("entry_zone") or {}
    claim: dict[str, Any] = {
        "claim_id": stable_id("SETUP_CLAIM", opportunity_id, strictness),
        "decision_type": "SETUP",
        "decision_subtype": "CONDITIONAL_SETUP",
        "direction": "BULLISH" if side == "BUY" else "BEARISH",
        "action": "SETUP",
        "role": "PRIMARY",
        "semantic_opportunity_id": opportunity_id,
        "variant_id": strictness,
        "generation_id": generation_id,
        "setup_horizon": setup_horizon,
        "strictness": strictness,
        "side": side,
        "entry": entry,
        "stop": stop,
        "scoring_target": target,
        "expiry_time": _iso(outcome_expiry),
        "horizons": [str(horizon["evaluation_horizon"])],
        "timeframe_scope": [str(horizon["activation_tf"]), *list(horizon["context_tfs"])],
        "labeling_policy_version": "CONDITIONAL_SINGLE_TARGET_V1",
        "activation": {
            "condition": condition,
            "reference_price_method": "ACTIVATION_BAR_CLOSE_MID",
            "atr_config": {
                "timeframe": horizon["activation_tf"],
                "period": 14,
                "method": "WILDER",
            },
            "expiry_time": _iso(activation_expiry),
        },
        "activation_policy": {
            "version": "FOUR_TIER_ACTIVATION_V1",
            "required_events": int(policy["required_events"]),
            "strictness_rank": int(policy["rank"]),
        },
        "invalidation": {
            "event_type": "CLOSED_BELOW" if side == "BUY" else "CLOSED_ABOVE",
            "timeframe": horizon["activation_tf"],
            "level": stop,
        },
        "regime": _market_context(decision_state, str(horizon["activation_tf"]))["regime"],
        "volatility": _market_context(decision_state, str(horizon["activation_tf"]))["volatility"],
        "geometry_provenance": {
            "zone_id": str(entry_zone.get("zone_id") or "UNAVAILABLE"),
            "zone_lower": geometry.get("entry", 0.0) if not entry_zone else _bound(entry_zone, "lower"),
            "zone_upper": geometry.get("entry", 0.0) if not entry_zone else _bound(entry_zone, "upper"),
            "target_zone_id": (geometry.get("target_zone") or {}).get("zone_id"),
            "buffer_method": "SPREAD_PLUS_ZONE_FRACTION",
            "buffer_value": geometry.get("buffer"),
            "minimum_rr": float(policy["min_rr"]),
            "policy_version": GEOMETRY_POLICY_VERSION,
        },
        "scorable_hint": bool(geometry["scorable"]),
        "non_scorable_reasons": [] if geometry["scorable"] else [geometry["reason"]],
    }
    return claim


def build_four_tier_setup_envelope(
    snapshot: dict[str, Any],
    decision_state: dict[str, Any],
) -> dict[str, Any]:
    _require_live_safe_snapshot(snapshot)
    if decision_state.get("snapshot_id") != snapshot.get("snapshot_id"):
        raise ValueError("setup matrix snapshot binding mismatch")
    generation_id = stable_id(
        "SETUP_GENERATION",
        snapshot["snapshot_id"],
        GEOMETRY_POLICY_VERSION,
    )
    blocking = sorted(
        {
            str(flag.get("code") or "UNKNOWN_BLOCK")
            for flag in decision_state.get("market_packet", {}).get("risk_flags", [])
            if flag.get("severity") == "BLOCK"
        }
    )
    claims = (
        []
        if blocking
        else [
            _build_claim(
                snapshot,
                decision_state,
                generation_id,
                setup_horizon,
                strictness,
                side,
            )
            for setup_horizon in HORIZONS
            for strictness in STRICTNESS
            for side in SIDES
        ]
    )
    return {
        "analysis_id": stable_id("ANALYSIS", generation_id, "CHAT_MODEL"),
        "view_id": stable_id("VIEW", generation_id, "CHAT_MODEL"),
        "snapshot_id": snapshot["snapshot_id"],
        "system": "CHAT_MODEL",
        "engine_version": "CHAT_SETUP_MATRIX_V1",
        "generation_id": generation_id,
        "setup_class": "NO_SETUP" if blocking else "CONDITIONAL_WATCH_SETUP",
        "block_reasons": blocking,
        "claims": claims,
    }


def setup_matrix_summary(envelope: dict[str, Any]) -> dict[str, Any]:
    claims = list(envelope.get("claims", []))
    return {
        "setup_class": str(envelope.get("setup_class") or "NO_SETUP"),
        "generation_id": str(envelope.get("generation_id") or ""),
        "variant_count": len(claims),
        "scorable_count": sum(claim.get("scorable_hint") is True for claim in claims),
        "non_scorable_count": sum(claim.get("scorable_hint") is not True for claim in claims),
    }
