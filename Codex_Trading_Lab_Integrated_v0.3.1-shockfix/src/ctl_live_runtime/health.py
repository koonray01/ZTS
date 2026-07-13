from __future__ import annotations

from typing import Any


def evaluate_health(
    snapshot: dict[str, Any],
    *,
    pipeline_errors: int,
    queue_ok: bool,
    audit_ok: bool,
    require_live_source: bool = True,
) -> dict[str, Any]:
    issues = []
    critical = []

    if snapshot["freshness"]["status"] != "FRESH":
        critical.append(f"SNAPSHOT_{snapshot['freshness']['status']}")
    if snapshot["qc"]["decision"] != "PASS":
        critical.append(f"SNAPSHOT_QC_{snapshot['qc']['decision']}")
    if require_live_source and snapshot.get("source") != "LIVE_MT5":
        critical.append("SNAPSHOT_SOURCE_NOT_LIVE_MT5")
    if pipeline_errors >= 3:
        critical.append("PIPELINE_ERROR_THRESHOLD")
    elif pipeline_errors > 0:
        issues.append("PIPELINE_RECENT_ERROR")
    if not queue_ok:
        critical.append("JOB_QUEUE_INTEGRITY")
    if not audit_ok:
        critical.append("AUDIT_CHAIN_INTEGRITY")

    if critical:
        return {"status": "CRITICAL", "issues": critical + issues}
    if issues:
        return {"status": "DEGRADED", "issues": issues}
    return {"status": "HEALTHY", "issues": []}
