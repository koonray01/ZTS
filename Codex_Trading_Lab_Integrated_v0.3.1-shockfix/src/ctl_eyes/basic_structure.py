from __future__ import annotations

from .base import SensorOutputBuilder
from .models import SensorContext
from .utils import find_confirmed_swings, ordered_structure_from_swings


def analyze_basic_structure(context: SensorContext) -> dict:
    builder = SensorOutputBuilder(context, "basic_structure", "0.1.0", "STRUCTURE")
    scales = {"INTERNAL": 2, "SWING": 4, "EXTERNAL": 6}
    structures = {}
    details = {}
    for name, width in scales.items():
        highs, lows = find_confirmed_swings(context.bars, left=width, right=width)
        result = ordered_structure_from_swings(highs, lows)
        structures[name] = result["state"]
        details[name] = result

    preferred = details["SWING"]
    if preferred["state"] == "UNKNOWN":
        preferred = details["INTERNAL"]
    directional = {state for state in structures.values() if state in {"BULLISH", "BEARISH"}}
    state = "TRANSITION" if len(directional) > 1 else preferred["state"]
    if state == "UNKNOWN":
        builder.status = "UNSCORABLE"
        builder.unknown(
            "INSUFFICIENT_CONFIRMED_SWINGS",
            "Need two temporally alternating confirmed highs and lows at at least one scale.",
            True,
        )
        return builder.build()
    evidence = list(dict.fromkeys(ref for detail in details.values() for pivot in detail["pivots"] for ref in pivot["evidence_refs"]))
    structure_id = builder.derive(
        "structure_by_scale",
        structures,
        "ORDERED_MULTI_SCALE_STRUCTURE_V0_2",
        [pivot["bar"].bar_id for detail in details.values() for pivot in detail["pivots"]],
        evidence,
    )
    builder.derive(
        "structure_state",
        state,
        "ORDERED_MULTI_SCALE_STRUCTURE_V0_2",
        [structure_id],
        evidence,
    )
    return builder.build()
