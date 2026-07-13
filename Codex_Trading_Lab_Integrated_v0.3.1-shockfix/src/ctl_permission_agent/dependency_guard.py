from __future__ import annotations

from typing import Any

from .models import GateResult
from .policy import REQUIRED_DEPENDENCIES


def check_dependencies(state: dict[str, Any]) -> GateResult:
    mismatches = []
    unknown = []
    for key, required in REQUIRED_DEPENDENCIES.items():
        actual = state.get(key)
        if actual is None:
            unknown.append(key)
        elif actual != required:
            mismatches.append(f"{key}: expected {required}, got {actual}")

    if mismatches:
        return GateResult(
            "G_DEPENDENCY",
            "INVALID",
            "Dependency mismatch: " + "; ".join(mismatches),
            True,
        )
    if unknown:
        return GateResult(
            "G_DEPENDENCY",
            "WAIT",
            "Dependency status unavailable: " + ", ".join(unknown),
            True,
        )
    return GateResult(
        "G_DEPENDENCY",
        "PASS",
        "All required versions match.",
        False,
    )
