from __future__ import annotations

from typing import Any


MINIMUM_OBSERVATIONS_FOR_REVIEW = 20


def summarize_visual_parity_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    overall_counts: dict[str, int] = {}
    by_timeframe: dict[str, dict[str, int]] = {}
    for report in reports:
        status = report.get("overall_status", "UNKNOWN")
        overall_counts[status] = overall_counts.get(status, 0) + 1
        for item in report.get("timeframes", []):
            timeframe = item.get("timeframe", "UNKNOWN")
            status = item.get("status", "UNKNOWN")
            bucket = by_timeframe.setdefault(timeframe, {})
            bucket[status] = bucket.get(status, 0) + 1
    count = len(reports)
    return {
        "schema_version": "0.1.0",
        "observation_count": count,
        "minimum_observations_for_review": MINIMUM_OBSERVATIONS_FOR_REVIEW,
        "calibration_status": "READY_FOR_REVIEW" if count >= MINIMUM_OBSERVATIONS_FOR_REVIEW else "INSUFFICIENT_DATA",
        "overall_status_counts": overall_counts,
        "timeframe_status_counts": by_timeframe,
        "interpretation": (
            "Visual parity reports are QA evidence only and do not establish trading expectancy."
        ),
    }
