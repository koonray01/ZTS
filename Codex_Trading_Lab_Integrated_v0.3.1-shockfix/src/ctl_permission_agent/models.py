from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Part3Context:
    snapshot: dict[str, Any]
    market_packet: dict[str, Any]
    scenario_packet: dict[str, Any]
    entry_packet: dict[str, Any]
    candidate: dict[str, Any]
    account: dict[str, Any]
    risk_policy: dict[str, Any]
    dependency_state: dict[str, Any]
    prior_decision_ids: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    status: str
    message: str
    blocking: bool
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "message": self.message,
            "blocking": self.blocking,
            "evidence_refs": list(self.evidence_refs),
        }
