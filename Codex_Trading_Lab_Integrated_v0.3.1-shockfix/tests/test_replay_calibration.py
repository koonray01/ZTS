from __future__ import annotations

from ctl_replay_training import summarize_candidate_quality


def _record(*, classification: str, realized_r: float, partition: str = "DEV", credit: bool = True, process_pass: bool = True) -> dict:
    return {
        "score": {
            "entry_engine_credit": credit,
            "process_pass": process_pass,
            "deterministic_fail": not process_pass,
            "outcome": {
                "classification": classification,
                "realized_r": realized_r,
                "clean_win": classification == "TP_FIRST" and realized_r > 0,
            },
        },
        "episode": {"partition": partition},
    }


def test_candidate_quality_separates_process_and_outcomes():
    report = summarize_candidate_quality([
        _record(classification="TP_FIRST", realized_r=1.8),
        _record(classification="NO_TRIGGER", realized_r=0.0, credit=False),
        _record(classification="SL_FIRST", realized_r=-1.0, process_pass=False),
    ])
    assert report["calibration_status"] == "INSUFFICIENT_DATA"
    assert report["coverage"]["credited_system_candidates"] == 2
    assert report["coverage"]["resolved_system_candidates"] == 2
    assert report["process_quality"]["process_pass_count"] == 2
    assert report["candidate_outcomes"]["net_r"] == 0.8
    assert report["candidate_outcomes"]["win_rate_resolved"] is None
    assert report["candidate_outcomes"]["statistical_metrics_suppressed"] is True
    assert report["trading_edge_established"] is False
    assert report["execution_permission_effect"] == "NONE"


def test_candidate_quality_requires_oos_and_blocks_excess_ambiguity():
    ready = [
        _record(classification="TP_FIRST" if index % 2 == 0 else "SL_FIRST", realized_r=1.5 if index % 2 == 0 else -1.0, partition="LOCKED_OOS" if index < 10 else "DEV")
        for index in range(30)
    ]
    ready_report = summarize_candidate_quality(ready)
    assert ready_report["calibration_status"] == "READY_FOR_REVIEW"
    assert ready_report["candidate_outcomes"]["win_rate_resolved"] == 0.5
    ambiguous = ready + [
        _record(classification="AMBIGUOUS_SAME_BAR", realized_r=0.0, partition="LOCKED_OOS")
        for _ in range(5)
    ]
    assert summarize_candidate_quality(ambiguous)["calibration_status"] == "DATA_QUALITY_BLOCK"
