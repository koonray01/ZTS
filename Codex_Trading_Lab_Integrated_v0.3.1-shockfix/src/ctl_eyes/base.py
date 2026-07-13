from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import SensorContext
from .utils import sanitize_id


@dataclass
class SensorOutputBuilder:
    context: SensorContext
    sensor_name: str
    sensor_version: str
    category: str
    status: str = "PASS"
    facts: list[dict[str, Any]] = field(default_factory=list)
    derived: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    unknowns: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    _counter: int = 0

    def _id(self, kind: str) -> str:
        self._counter += 1
        return sanitize_id(
            f"{kind}_{self.sensor_name}_{self.context.timeframe}_{self.context.snapshot_id}_{self._counter}"
        )

    def fact(
        self,
        name: str,
        value: Any,
        evidence_refs: list[str],
        unit: str | None = None,
    ) -> str:
        claim_id = self._id("FACT")
        self.facts.append(
            {
                "claim_id": claim_id,
                "name": name,
                "value": value,
                "unit": unit,
                "evidence_refs": list(dict.fromkeys(evidence_refs)),
            }
        )
        return claim_id

    def derive(
        self,
        name: str,
        value: Any,
        checker_id: str,
        input_refs: list[str],
        evidence_refs: list[str],
    ) -> str:
        claim_id = self._id("DERIVED")
        self.derived.append(
            {
                "claim_id": claim_id,
                "name": name,
                "value": value,
                "checker_id": checker_id,
                "input_refs": list(dict.fromkeys(input_refs)),
                "evidence_refs": list(dict.fromkeys(evidence_refs)),
            }
        )
        return claim_id

    def event(
        self,
        event_type: str,
        status: str,
        direction: str,
        evidence_refs: list[str],
        *,
        level: float | None = None,
        band: dict[str, float] | None = None,
        closed_bar_confirmed: bool = True,
        first_seen_at: str | None = None,
        confirmed_at: str | None = None,
        label: str | None = None,
    ) -> str:
        event_id = self._id("EVENT")
        self.events.append(
            {
                "event_id": event_id,
                "event_type": event_type,
                "status": status,
                "direction": direction,
                "level": level,
                "band": band,
                "closed_bar_confirmed": closed_bar_confirmed,
                "first_seen_at": first_seen_at,
                "confirmed_at": confirmed_at,
                "label": label,
                "evidence_refs": list(dict.fromkeys(evidence_refs)),
            }
        )
        return event_id

    def unknown(self, code: str, message: str, blocking: bool) -> None:
        self.unknowns.append({"code": code, "message": message, "blocking": blocking})
        if blocking and self.status == "PASS":
            self.status = "BLOCKED"
        elif self.status == "PASS":
            self.status = "PARTIAL"

    def build(self, runtime_ms: int = 0) -> dict[str, Any]:
        evidence_refs = list(
            dict.fromkeys(
                list(self.context.snapshot_evidence_refs)
                + [ref for item in self.facts for ref in item["evidence_refs"]]
                + [ref for item in self.derived for ref in item["evidence_refs"]]
                + [ref for item in self.events for ref in item["evidence_refs"]]
            )
        )
        if not evidence_refs:
            evidence_refs = [sanitize_id(f"EVID_{self.context.snapshot_id}")]

        return {
            "schema_version": "0.2.0",
            "sensor_result_id": sanitize_id(
                f"SENSOR_{self.sensor_name}_{self.context.timeframe}_{self.context.snapshot_id}"
            ),
            "run_id": self.context.run_id,
            "snapshot_id": self.context.snapshot_id,
            "sensor": {
                "name": self.sensor_name,
                "version": self.sensor_version,
                "category": self.category,
            },
            "symbol": self.context.symbol,
            "timeframe": self.context.timeframe,
            "status": self.status,
            "facts": self.facts,
            "derived": self.derived,
            "events": self.events,
            "unknowns": self.unknowns,
            "warnings": self.warnings,
            "errors": self.errors,
            "evidence_refs": evidence_refs,
            "generated_at": self.context.capture_time,
            "runtime_ms": max(0, int(runtime_ms)),
        }


def blocked_output(
    context: SensorContext,
    sensor_name: str,
    category: str,
    code: str,
    message: str,
) -> dict[str, Any]:
    builder = SensorOutputBuilder(context, sensor_name, "0.1.0", category, status="BLOCKED")
    builder.unknown(code, message, True)
    return builder.build()
