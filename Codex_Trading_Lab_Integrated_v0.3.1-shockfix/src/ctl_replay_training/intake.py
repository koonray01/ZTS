from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("payload", data)


def _intake_id(snapshot_id: str) -> str:
    digest = hashlib.sha256(snapshot_id.encode("utf-8")).hexdigest()[:16]
    return f"INTAKE_{digest}"


def build_replay_intake(
    normalized_root: str | Path,
    *,
    partition: str = "FORWARD_SHADOW",
    symbol: str = "XAUUSD",
) -> dict[str, Any]:
    root = Path(normalized_root)
    paths = sorted(root.rglob("decision_state.json"))
    records: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    for path in paths:
        payload = _payload(path)
        market = payload.get("market_packet", {})
        quality = market.get("data_quality", {})
        source = quality.get("source")
        if payload.get("symbol", market.get("symbol", symbol)) != symbol:
            continue
        if source != "LIVE_MT5":
            raise ValueError(f"Replay intake requires LIVE_MT5 source: {path}")
        source_counts[source] += 1
        candidates = []
        for candidate in payload.get("entry_packet", {}).get("candidates", []):
            candidates.append({
                "candidate_id": candidate.get("candidate_id"),
                "scenario_id": candidate.get("scenario_id"),
                "entry_type": candidate.get("entry_type"),
                "side": candidate.get("side"),
                "status": candidate.get("status"),
                "entry_range": candidate.get("entry_range"),
                "stop": candidate.get("stop"),
                "targets": candidate.get("targets", []),
                "rr": candidate.get("rr"),
                "trigger": candidate.get("trigger"),
                "expiry": candidate.get("expiry"),
                "hard_requirements": candidate.get("hard_requirements", []),
                "evidence_refs": candidate.get("evidence_refs", []),
            })
        records.append({
            "intake_id": _intake_id(payload["snapshot_id"]),
            "snapshot_id": payload["snapshot_id"],
            "capture_time": market.get("generated_at"),
            "symbol": symbol,
            "source": source,
            "partition": partition,
            "data_quality": quality,
            "market_state": [
                {
                    "timeframe": item.get("timeframe"),
                    "structure": item.get("structure"),
                    "regime": item.get("regime"),
                    "recent_leg": item.get("recent_leg"),
                    "phase": item.get("phase"),
                    "volatility": item.get("volatility"),
                }
                for item in market.get("market_state", [])
            ],
            "location": {
                key: market.get("location", {}).get(key)
                for key in ("status", "structural_reference_price", "live_mid", "live_bid", "live_ask", "labels")
            },
            "risk_flags": market.get("risk_flags", []),
            "conflicts": market.get("conflicts", []),
            "candidates": candidates,
            "outcome_status": "UNLABELED",
            "outcome_classification": None,
            "realized_r": None,
            "outcome_source": None,
        })
    records.sort(key=lambda item: item.get("capture_time") or item["snapshot_id"])
    return {
        "schema_version": "0.1.0",
        "mode": "FORWARD_SHADOW_INTAKE",
        "symbol": symbol,
        "partition": partition,
        "source": "LIVE_MT5",
        "records": records,
        "summary": {
            "snapshot_count": len(records),
            "snapshots_with_candidates": sum(1 for item in records if item["candidates"]),
            "candidate_count": sum(len(item["candidates"]) for item in records),
            "ready_candidate_count": sum(
                1 for item in records for candidate in item["candidates"]
                if candidate.get("status") == "READY_FOR_PERMISSION_REVIEW"
            ),
            "labeled_outcome_count": sum(1 for item in records if item["outcome_status"] != "UNLABELED"),
            "source_counts": dict(sorted(source_counts.items())),
        },
        "readiness": "OUTCOME_LABELING_REQUIRED",
        "execution_permission_effect": "NONE",
        "limitations": [
            "This ledger is an intake artifact; it does not invent hidden outcomes.",
            "Outcome labels require later closed-bar review with an independent labeling process.",
            "The ledger cannot establish trading edge or grant execution permission.",
        ],
    }
