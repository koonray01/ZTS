from __future__ import annotations

import copy

from ctl_decision_core import diff_decision_state, run_decision_core
from ctl_decision_core.entry_engine import _select_zone, build_entry_packet
from ctl_decision_core.fusion import (
    _is_available_at_capture,
    _opposing_armed_opportunity_conflict,
    _select_working_zones,
    _structure_value,
    _zone_from_fvg,
    _zone_from_ob,
)
from ctl_decision_core.helpers import choose_target
from ctl_eyes.utils import ordered_structure_from_swings
from ctl_visual_parity import compare_visual_observation, summarize_visual_parity_reports


def _zone(zone_id: str, zone_type: str, lower: float, upper: float, freshness: str = "FRESH") -> dict:
    return {
        "zone_id": zone_id,
        "zone_type": zone_type,
        "lower": lower,
        "upper": upper,
        "status": "ACTIVE",
        "freshness": freshness,
        "evidence_refs": [zone_id],
    }


def test_zone_selection_requires_price_proximity_before_freshness() -> None:
    market = {
        "active_zones": [
            _zone("ZONE_FAR", "SUPPLY", 120.0, 121.0, "FRESH"),
            _zone("ZONE_NEAR", "SUPPLY", 101.0, 102.0, "USED"),
        ]
    }

    selected = _select_zone(market, "SELL", reference_price=100.9)

    assert selected is not None
    assert selected["zone_id"] == "ZONE_NEAR"


def test_target_is_resolved_from_entry_not_packet_level_market_price() -> None:
    liquidity = {
        "nearest_above": 130.0,
        "nearest_below": 80.0,
        "pools": [
            {"lower": 99.0, "upper": 100.0},
            {"lower": 89.0, "upper": 90.0},
        ],
    }

    target, basis = choose_target("SELL", entry=110.0, stop=112.0, liquidity=liquidity)

    assert target == 100.0
    assert basis == "nearest opposite liquidity"


def test_limit_candidate_with_unresolved_retest_cannot_be_ready() -> None:
    market = {
        "active_zones": [_zone("ZONE_BUY", "SUPPORT", 99.0, 100.0)],
        "location": {"reference_price": 99.5, "labels": [], "status": "KNOWN", "evidence_refs": ["ZONE_BUY"]},
        "liquidity": {
            "nearest_above": 105.0,
            "nearest_below": 95.0,
            "pools": [{"lower": 105.0, "upper": 105.5}],
            "evidence_refs": ["LIQ_001"],
        },
        "risk_flags": [],
        "conflicts": [],
        "market_state": [],
        "run_id": "RUN_TEST",
        "snapshot_id": "SNAP_TEST",
        "symbol": "XAUUSD",
        "generated_at": "2026-07-13T10:00:00Z",
        "market_packet_id": "MARKET_TEST",
        "evidence_refs": ["EVID_TEST"],
    }
    scenarios = {
        "scenario_packet_id": "SCENARIO_TEST",
        "scenarios": [
            {
                "scenario_id": "SCN_TEST",
                "rank": "PRIMARY",
                "direction": "BULLISH",
                "candidate_entry_types": ["STRUCTURED_LIMIT"],
                "missing_events": ["RETEST_HOLD"],
                "required_events": ["SWEEP_LOW", "RECLAIM_BULLISH", "RETEST_HOLD"],
                "evidence_refs": ["EVID_TEST"],
            }
        ],
        "evidence_refs": ["EVID_TEST"],
    }

    packet = build_entry_packet(market, scenarios)
    candidate = packet["candidates"][0]

    assert candidate["limit_eligibility"] == "LIMIT_READY"
    assert candidate["status"] == "WAIT"
    assert candidate["missing_conditions"] == ["RETEST_HOLD"]


def test_live_quote_outside_zone_blocks_location_even_when_closed_reference_was_inside() -> None:
    market = {
        "active_zones": [_zone("ZONE_BUY", "SUPPORT", 99.0, 100.0)],
        "location": {
            "reference_price": 99.5,
            "structural_reference_price": 99.5,
            "live_mid": 102.0,
            "labels": [], "status": "KNOWN", "evidence_refs": ["ZONE_BUY"],
        },
        "liquidity": {"nearest_above": 105.0, "nearest_below": 95.0, "pools": [{"lower": 105.0, "upper": 105.5}], "evidence_refs": ["LIQ_001"]},
        "risk_flags": [], "conflicts": [], "market_state": [], "run_id": "RUN_TEST", "snapshot_id": "SNAP_TEST",
        "symbol": "XAUUSD", "generated_at": "2026-07-13T10:00:00Z", "market_packet_id": "MARKET_TEST", "evidence_refs": ["EVID_TEST"],
    }
    scenarios = {"scenario_packet_id": "SCENARIO_TEST", "evidence_refs": ["EVID_TEST"], "scenarios": [{
        "scenario_id": "SCN_TEST", "rank": "PRIMARY", "direction": "BULLISH", "candidate_entry_types": ["STRUCTURED_LIMIT"],
        "missing_events": [], "required_events": [], "evidence_refs": ["EVID_TEST"],
    }]}

    candidate = build_entry_packet(market, scenarios)["candidates"][0]

    assert candidate["status"] == "WAIT"
    assert candidate["limit_eligibility"] == "LIMIT_WATCH"
    assert "PRICE_LEFT_LOCATION" in candidate["missing_conditions"]
    assert next(item for item in candidate["hard_requirements"] if item["requirement_id"] == "LOCATION")["status"] == "PENDING"


def test_opposing_armed_opportunities_create_blocking_conflict() -> None:
    conflict = _opposing_armed_opportunity_conflict("XAUUSD", [
        {"timeframe": "H4", "setup_family": "SR1", "direction": "BUY", "status": "ARMED"},
        {"timeframe": "M5", "setup_family": "SR1", "direction": "SELL", "status": "READY_FOR_ENTRY_EVALUATION"},
    ])

    assert conflict is not None
    assert conflict["blocking"] is True
    assert "OPPOSING_ARMED_OPPORTUNITIES" in conflict["conflict_id"]


def test_working_zone_selection_is_bounded_and_keeps_nearest_quality_zone() -> None:
    zones = [
        {
            "zone_id": f"ZONE_M5_{index}", "timeframe": "M5", "zone_type": "SUPPORT",
            "lower": 99.0 + index, "upper": 99.4 + index, "status": "ACTIVE",
            "freshness": "FRESH" if index == 0 else "USED", "source_type": "SUPPORT_RESISTANCE", "evidence_refs": ["EVID_TEST"],
        }
        for index in range(10)
    ]
    zones.append({**zones[0], "zone_id": "ZONE_INVALID", "status": "INVALIDATED"})

    selected = _select_working_zones(zones, reference_price=99.2)

    assert len(selected) == 8
    assert selected[0]["zone_id"] == "ZONE_M5_0"
    assert "ZONE_INVALID" not in {zone["zone_id"] for zone in selected}


def test_visual_parity_is_qa_only_and_flags_live_price_mismatch() -> None:
    market = {
        "symbol": "XAUUSD", "market_packet_id": "MARKET_TEST",
        "location": {"live_mid": 100.0},
        "market_state": [{"timeframe": "M5", "structure": "BEARISH", "recent_leg": "BEARISH_ROTATION"}],
        "active_zones": [{"timeframe": "M5", "zone_type": "SUPPORT", "lower": 99.0, "upper": 100.0}],
    }
    observation = {
        "observation_id": "OBS_TEST", "timeframes": [{
            "timeframe": "M5", "visible_price": 103.0,
            "structure": {"internal": "BEARISH", "external": "BEARISH"},
            "recent_leg": "BEARISH_IMPULSE", "zones": [{"zone_type": "SUPPORT", "lower": 99.5, "upper": 100.5}],
        }], "price_tolerance": 1.0,
    }

    report = compare_visual_observation(market, observation)

    assert report["mode"] == "QA_ONLY_NO_PERMISSION_EFFECT"
    assert report["overall_status"] == "MISMATCH"
    assert report["timeframes"][0]["structure"]["status"] == "MATCH"
    assert report["timeframes"][0]["price"]["status"] == "MISMATCH"


def test_visual_parity_calibration_refuses_small_sample() -> None:
    summary = summarize_visual_parity_reports([
        {"overall_status": "MATCH", "timeframes": [{"timeframe": "M5", "status": "MATCH"}]},
        {"overall_status": "PARTIAL_MATCH", "timeframes": [{"timeframe": "M5", "status": "PARTIAL_MATCH"}]},
    ])

    assert summary["observation_count"] == 2
    assert summary["calibration_status"] == "INSUFFICIENT_DATA"
    assert summary["timeframe_status_counts"]["M5"] == {"MATCH": 1, "PARTIAL_MATCH": 1}


def test_market_packet_uses_m5_as_execution_reference_price(state: dict) -> None:
    snapshot = state["snapshot"]
    m5_close = next(item for item in snapshot["timeframes"] if item["timeframe"] == "M5")["bars"][-1]["close"]

    assert state["market_packet"]["location"]["reference_price"] == m5_close
    assert all(item["regime"] in {"TREND", "RANGE", "TRANSITION", "UNKNOWN"} for item in state["market_packet"]["market_state"])
    assert all(item["recent_leg"] for item in state["market_packet"]["market_state"])


def test_ordered_structure_collapses_same_side_pivots_before_classification() -> None:
    highs = [
        {"index": 1, "level": 110.0},
        {"index": 2, "level": 112.0},  # Consecutive high: retain this extreme.
        {"index": 5, "level": 115.0},
    ]
    lows = [
        {"index": 3, "level": 100.0},
        {"index": 4, "level": 99.0},  # Consecutive low: retain this extreme.
        {"index": 6, "level": 103.0},
    ]

    result = ordered_structure_from_swings(highs, lows)

    assert [item["index"] for item in result["pivots"]] == [2, 4, 5, 6]
    assert result["high_sequence"] == "HH"
    assert result["low_sequence"] == "HL"
    assert result["state"] == "BULLISH"


def test_conflicting_multi_scale_structure_is_transition_not_directional() -> None:
    result = {"derived": [{"name": "structure_by_scale", "value": {"INTERNAL": "BEARISH", "SWING": "BULLISH", "EXTERNAL": "BULLISH"}}]}

    assert _structure_value(result) == "TRANSITION"


def test_fvg_and_order_block_map_to_causal_active_zones() -> None:
    gap = {
        "gap_id": "FVG_M5_001", "direction": "BULLISH", "lower": 100.0, "upper": 101.0,
        "status": "ACTIVE", "touched": False, "available_at": "2026-07-13T10:00:00Z", "evidence_refs": ["BAR_001"],
    }
    ob = {
        "candidate_id": "OB_M5_001", "direction": "BEARISH", "lower": 110.0, "upper": 111.0,
        "available_at": "2026-07-13T10:01:00Z", "evidence_refs": ["BAR_002"],
    }

    mapped_gap = _zone_from_fvg(gap, "M5")
    mapped_ob = _zone_from_ob(ob, "M5")

    assert (mapped_gap["zone_type"], mapped_gap["status"], mapped_gap["source_type"]) == ("DEMAND", "ACTIVE", "FAIR_VALUE_GAP")
    assert (mapped_ob["zone_type"], mapped_ob["source_type"]) == ("SUPPLY", "ORDER_BLOCK_CANDIDATE")
    assert _is_available_at_capture(mapped_gap, "2026-07-13T10:00:00Z") is True
    assert _is_available_at_capture(mapped_ob, "2026-07-13T10:00:30Z") is False


def test_semantic_entities_survive_snapshot_identity_change(snapshot: dict) -> None:
    first = run_decision_core(snapshot)
    next_snapshot = copy.deepcopy(snapshot)
    next_snapshot["snapshot_id"] = "SNAP_SEMANTIC_NEXT"
    next_snapshot["run_id"] = "RUN_SEMANTIC_NEXT"
    next_snapshot["capture_time"] = "2025-03-06T00:05:00Z"
    second = run_decision_core(next_snapshot)

    first_zones = {item["zone_id"] for item in first["market_packet"]["active_zones"]}
    second_zones = {item["zone_id"] for item in second["market_packet"]["active_zones"]}
    first_scenarios = {item["scenario_id"] for item in first["scenario_packet"]["scenarios"]}
    second_scenarios = {item["scenario_id"] for item in second["scenario_packet"]["scenarios"]}

    assert first_zones == second_zones
    assert first_scenarios == second_scenarios


def test_watcher_detects_status_transition_for_stable_candidate_id(snapshot: dict) -> None:
    previous = run_decision_core(snapshot)
    current = copy.deepcopy(previous)
    candidate = current["entry_packet"]["candidates"][0]
    candidate["status"] = "READY_FOR_PERMISSION_REVIEW"

    watcher = diff_decision_state(previous, current)

    assert any(event["event_type"] == "ENTRY_WINDOW_OPENED" for event in watcher["significant_events"])
