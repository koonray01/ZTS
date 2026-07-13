from __future__ import annotations

from typing import Any


def evaluate_limit_eligibility(
    *,
    zone: dict[str, Any] | None,
    rr: float,
    risk_flags: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    invalidation_clear: bool,
    at_location: bool = True,
) -> tuple[str, list[dict[str, str]]]:
    checks: list[dict[str, str]] = []

    def add(requirement_id: str, status: str, message: str) -> None:
        checks.append({"requirement_id": requirement_id, "status": status, "message": message})

    if zone is None:
        add("LIMIT_ZONE", "FAIL", "No traceable zone was available.")
        return "LIMIT_REJECTED", checks

    if zone["status"] in {"INVALIDATED", "EXPIRED"}:
        add("LIMIT_ZONE", "FAIL", "Zone is invalidated or expired.")
        return "LIMIT_INVALIDATED", checks

    add("LIMIT_ZONE", "PASS", "Zone is traceable and active.")
    add(
        "PRICE_AT_LOCATION",
        "PASS" if at_location else "PENDING",
        "Price is at the selected zone." if at_location else "Price has not reached the selected zone.",
    )
    if zone["freshness"] == "FRESH":
        add("ZONE_FRESHNESS", "PASS", "Zone is fresh.")
    elif zone["freshness"] == "USED":
        add("ZONE_FRESHNESS", "PENDING", "Zone has been used; confirmation is preferred.")
    else:
        add("ZONE_FRESHNESS", "FAIL", "Zone is heavily used or freshness is unknown.")

    if rr >= 1.5:
        add("MINIMUM_RR", "PASS", f"RR {rr:.2f} meets the research threshold.")
    else:
        add("MINIMUM_RR", "FAIL", f"RR {rr:.2f} is below 1.50.")

    blocking_risk = any(flag["severity"] == "BLOCK" for flag in risk_flags)
    add(
        "NO_BLOCKING_RISK",
        "FAIL" if blocking_risk else "PASS",
        "Blocking risk exists." if blocking_risk else "No blocking risk flag.",
    )
    blocking_conflict = any(conflict["blocking"] for conflict in conflicts)
    add(
        "NO_BLOCKING_CONFLICT",
        "FAIL" if blocking_conflict else "PASS",
        "Blocking conflict exists." if blocking_conflict else "No blocking conflict.",
    )
    add(
        "CLEAR_INVALIDATION",
        "PASS" if invalidation_clear else "FAIL",
        "Structural invalidation is explicit." if invalidation_clear else "Invalidation is unclear.",
    )

    statuses = {item["status"] for item in checks}
    if "FAIL" in statuses:
        if blocking_risk or blocking_conflict:
            return "CONFIRMATION_REQUIRED", checks
        return "LIMIT_REJECTED", checks
    if "PENDING" in statuses:
        return "LIMIT_WATCH", checks
    return "LIMIT_READY", checks
