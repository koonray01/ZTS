from __future__ import annotations

from typing import Any

from .models import Bar, SensorContext
from .utils import ensure_closed_valid_bars


class SnapshotContractError(ValueError):
    pass


def contexts_from_snapshot(snapshot: dict[str, Any]) -> list[SensorContext]:
    required = ["schema_version", "snapshot_id", "run_id", "symbol", "capture_time", "timeframes"]
    missing = [key for key in required if key not in snapshot]
    if missing:
        raise SnapshotContractError(f"Missing snapshot fields: {missing}")
    if snapshot["schema_version"] not in {"0.2.0", "0.3.0"}:
        raise SnapshotContractError("Unsupported snapshot schema version")

    contexts: list[SensorContext] = []
    for timeframe_data in snapshot["timeframes"]:
        bars = tuple(Bar.from_dict(item) for item in timeframe_data["bars"])
        errors = ensure_closed_valid_bars(bars)
        if errors:
            raise SnapshotContractError(";".join(errors))
        contexts.append(
            SensorContext(
                schema_version=snapshot["schema_version"],
                snapshot_id=snapshot["snapshot_id"],
                run_id=snapshot["run_id"],
                symbol=snapshot["symbol"],
                timeframe=timeframe_data["timeframe"],
                capture_time=snapshot["capture_time"],
                bars=bars,
                snapshot_evidence_refs=tuple(snapshot.get("evidence_refs", [])),
            )
        )
    return contexts
