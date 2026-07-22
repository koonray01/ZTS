from __future__ import annotations

from ctl_analysis_registry.abstention import label_abstention


def _decision(*, with_control=True, action="HOLD"):
    result = {
        "decision_id": "ABSTAIN_1", "system": "ZENITH", "decision_type": "ABSTENTION",
        "action": action, "labeling_policy_version": "FROZEN_CONTROL_V1",
        "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0},
    }
    if with_control:
        result["frozen_control"] = {"entry": 100.0, "stop": 99.0, "scoring_target": 102.0, "expiry_time": "2026-07-22T11:00:00Z"}
    return result


def test_general_hold_without_frozen_control_is_not_scorable() -> None:
    assert label_abstention(_decision(with_control=False), None)["classification"] == "NOT_SCORABLE"


def test_rejected_candidate_that_would_hit_sl_is_protected_from_loss() -> None:
    result = label_abstention(_decision(), {"classification": "SL_FIRST"})
    assert result["classification"] == "PROTECTED_FROM_LOSS"


def test_rejected_candidate_that_would_hit_tp_is_missed_winner() -> None:
    result = label_abstention(_decision(), {"classification": "TP_FIRST"})
    assert result["classification"] == "MISSED_WINNER"


def test_untriggered_control_is_correct_patience() -> None:
    result = label_abstention(_decision(), {"classification": "EXPIRED_UNTRIGGERED"})
    assert result["classification"] == "CORRECT_PATIENCE"


def test_wait_that_delayed_a_winner_is_unnecessary_delay() -> None:
    result = label_abstention(_decision(action="WAIT"), {"classification": "TP_FIRST"})
    assert result["classification"] == "UNNECESSARY_DELAY"


def test_unresolved_control_is_no_material_opportunity() -> None:
    result = label_abstention(_decision(), {"classification": "UNRESOLVED"})
    assert result["classification"] == "NO_MATERIAL_OPPORTUNITY"
