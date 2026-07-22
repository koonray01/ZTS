from __future__ import annotations

import pytest

from ctl_analysis_registry.directional import label_directional


def _decision(*, direction="BULLISH", reference=100.0, atr=1.0, conditional=False):
    result = {
        "decision_id": "DECISION_1", "system": "ZENITH", "decision_type": "DIRECTIONAL",
        "decision_subtype": "CONDITIONAL_DIRECTIONAL" if conditional else "UNCONDITIONAL_DIRECTIONAL",
        "direction": direction, "labeling_policy_version": "DIRECTIONAL_TERMINAL_ATR_V1",
        "reference_price": {"method": "DECISION_TIME_MID", "value": reference},
        "atr": {"value": atr},
        "safety": {"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0},
    }
    return result


def _job(**overrides):
    job = {"job_id": "JOB_1", "horizon": "PT1H"}
    job.update(overrides)
    return job


def _evidence(*, terminal_mid=100.0, qc="PASS", reasons=None):
    return {
        "evidence_id": "EVIDENCE_1", "qc": {"status": qc, "reasons": reasons or []},
        "terminal": {"status": "PASS", "bar": {"mid_close": terminal_mid}},
        "bars": [
            {"mid_high": max(terminal_mid, 100.4), "mid_low": min(terminal_mid, 99.8)},
            {"mid_close": terminal_mid, "mid_high": terminal_mid, "mid_low": terminal_mid},
        ],
        "evidence_refs": ["EVIDENCE_1"],
    }


@pytest.mark.parametrize(
    ("terminal", "expected"),
    [(100.30, "CORRECT"), (99.70, "INCORRECT"), (100.10, "NEUTRAL")],
)
def test_directional_terminal_atr_v1(terminal, expected) -> None:
    result = label_directional(_decision(), _job(), _evidence(terminal_mid=terminal))

    assert result["classification"] == expected


def test_bearish_direction_inverts_signed_return() -> None:
    result = label_directional(_decision(direction="BEARISH"), _job(), _evidence(terminal_mid=99.7))
    assert result["classification"] == "CORRECT"


def test_conditional_uses_activation_values_not_decision_values() -> None:
    decision = _decision(reference=95.0, atr=5.0, conditional=True)
    job = _job(evaluation_reference_price=100.0, evaluation_atr=1.0)

    result = label_directional(decision, job, _evidence(terminal_mid=100.3))

    assert result["classification"] == "CORRECT"
    assert result["evaluation_reference_price"] == 100.0


def test_evidence_conflict_is_ambiguous_not_incorrect() -> None:
    result = label_directional(
        _decision(), _job(),
        _evidence(terminal_mid=99.0, qc="FAIL", reasons=["EVIDENCE_CONFLICT"]),
    )
    assert result["classification"] == "AMBIGUOUS"


def test_missing_terminal_bar_is_insufficient_followup() -> None:
    evidence = _evidence()
    evidence["terminal"] = {"status": "INSUFFICIENT_FOLLOWUP", "reason": "MARKET_CLOSURE_NO_TERMINAL_BAR"}

    assert label_directional(_decision(), _job(), evidence)["classification"] == "INSUFFICIENT_FOLLOWUP"
