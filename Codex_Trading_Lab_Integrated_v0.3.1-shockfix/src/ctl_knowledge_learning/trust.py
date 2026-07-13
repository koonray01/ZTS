from __future__ import annotations

TRUST_ORDER = {
    "LOCKED_CANONICAL_POLICY": 7,
    "DETERMINISTIC_CHECKER": 6,
    "VALIDATED_EVIDENCE": 5,
    "VALIDATED_RESEARCH": 4,
    "EPISODE_OBSERVATION": 3,
    "AI_INTERPRETATION": 2,
    "HYPOTHESIS": 1,
}


def trust_rank(tier: str) -> int:
    return TRUST_ORDER[tier]


def production_authoritative(record: dict) -> bool:
    return (
        record["trust_tier"] == "LOCKED_CANONICAL_POLICY"
        and record["record_type"] == "APPROVED_POLICY"
        and record["status"] == "LOCKED"
    )
