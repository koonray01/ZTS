from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import canonical_json, iso_z, sanitize_id, sha256_json


def record_manual_entry(
    path: str | Path,
    *,
    position_id: str,
    symbol: str,
    side: str,
    price: float,
    volume: float,
    stop: float | None,
    proposal: dict[str, Any] | None,
    observed_at: datetime,
) -> dict[str, Any]:
    origin = "SYSTEM_APPROVED" if proposal else "MANUAL_OVERRIDE"
    record = {
        "record_id": sanitize_id(f"ENTRY_RECORD_{position_id}_{iso_z(observed_at)}"),
        "position_id": position_id,
        "symbol": symbol,
        "side": side,
        "price": price,
        "volume": volume,
        "stop": stop,
        "entry_origin": origin,
        "system_entry_credit": origin == "SYSTEM_APPROVED",
        "proposal_id": None if proposal is None else proposal["proposal_id"],
        "decision_id": None if proposal is None else proposal["decision_id"],
        "decision_hash": None if proposal is None else proposal["decision_hash"],
        "observed_at": iso_z(observed_at),
    }
    record["record_hash"] = sha256_json(record)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(record) + "\n")
    return record
