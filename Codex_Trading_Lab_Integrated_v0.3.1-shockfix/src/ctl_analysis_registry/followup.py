"""Outcome-blind follow-up collection, temporal selection, and source QC."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .identity import canonical_json, sha256_hex, stable_id


_TIMEFRAME_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}


class EvidenceCollisionError(RuntimeError):
    """Raised when immutable evidence identity is reused with different bytes."""


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def eligible_bars(job: dict[str, Any], bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    start = _time(str(job["evaluation_start"]))
    deadline = _time(str(job["evaluation_deadline"]))
    timeframe = str(job["timeframe"])
    terminal_lag = int(job.get("max_terminal_lag_seconds", _TIMEFRAME_SECONDS.get(timeframe, 0)))
    latest_close = deadline + timedelta(seconds=terminal_lag)
    eligible = []
    for bar in bars:
        if bar.get("timeframe") != timeframe or bar.get("is_closed") is not True:
            continue
        try:
            open_time = _time(str(bar["open_time"]))
            close_time = _time(str(bar["close_time"]))
        except (KeyError, ValueError):
            continue
        if open_time >= start and close_time <= latest_close:
            eligible.append(deepcopy(bar))
    return sorted(eligible, key=lambda item: (str(item["open_time"]), str(item.get("bar_id") or "")))


def select_terminal_bar(job: dict[str, Any], bars: list[dict[str, Any]]) -> dict[str, Any]:
    deadline = _time(str(job["evaluation_deadline"]))
    lag = timedelta(seconds=int(job.get("max_terminal_lag_seconds", 0)))
    valid: list[tuple[datetime, dict[str, Any]]] = []
    for bar in bars:
        try:
            close_time = _time(str(bar["close_time"]))
        except (KeyError, ValueError):
            continue
        if bar.get("is_closed") is True and close_time <= deadline + lag:
            valid.append((close_time, bar))
    if not valid:
        return {"status": "INSUFFICIENT_FOLLOWUP", "reason": "MARKET_CLOSURE_NO_TERMINAL_BAR"}
    before = [item for item in valid if item[0] <= deadline]
    selected = max(before or valid, key=lambda item: item[0])
    return {"status": "PASS", "bar": deepcopy(selected[1])}


def cross_snapshot_qc(
    decision_binding: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    observed = evidence.get("source_binding") if isinstance(evidence.get("source_binding"), dict) else {}
    reasons: list[str] = []
    for field in ("source", "server", "symbol", "digits", "point", "broker_utc_offset_minutes"):
        if decision_binding.get(field) != observed.get(field):
            reasons.append(f"SOURCE_BINDING_MISMATCH:{field}")
    expected_overlap = decision_binding.get("overlap_fingerprint")
    observed_overlap = observed.get("overlap_fingerprint")
    if expected_overlap and observed_overlap and expected_overlap != observed_overlap:
        reasons.append("EVIDENCE_CONFLICT")
    return {"status": "PASS" if not reasons else "FAIL", "reasons": sorted(reasons)}


def reconstruct_prices(
    bars: list[dict[str, Any]],
    *,
    point: float | None,
    ticks: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    all_spreads_valid = bool(bars) and isinstance(point, (int, float)) and point > 0
    for source in bars:
        bar = deepcopy(source)
        spread = bar.get("spread_points")
        spread_valid = isinstance(spread, (int, float)) and spread >= 0 and all_spreads_valid
        if spread_valid:
            offset = float(spread) * float(point)
            for field in ("open", "high", "low", "close"):
                bid = bar.get(field)
                if isinstance(bid, (int, float)):
                    bar[f"bid_{field}"] = float(bid)
                    bar[f"ask_{field}"] = round(float(bid) + offset, 12)
                    bar[f"mid_{field}"] = round(float(bid) + offset / 2.0, 12)
        else:
            all_spreads_valid = False
            for field in ("open", "high", "low", "close"):
                value = bar.get(field)
                if isinstance(value, (int, float)):
                    bar[f"mid_{field}"] = float(value)
        normalized.append(bar)
    if ticks:
        quality = "TRUE_BID_ASK_TICKS"
    elif all_spreads_valid:
        quality = "BAR_SPREAD_RECONSTRUCTED"
    else:
        quality = "MID_ONLY_PROXY"
    return {"bars": normalized, "ticks": deepcopy(ticks), "price_quality": quality}


def _atomic_json(path: Path, value: Any) -> str:
    encoded = canonical_json(value).encode("utf-8")
    if path.exists():
        existing = path.read_bytes()
        if existing != encoded:
            raise EvidenceCollisionError(f"immutable evidence collision: {path}")
        return sha256_hex(existing)
    temporary = path.with_name(f".{path.name}.tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return sha256_hex(encoded)


def collect_followup(
    job: dict[str, Any],
    adapter: Any,
    output_root: str | Path,
) -> dict[str, Any]:
    start = _time(str(job["evaluation_start"]))
    deadline = _time(str(job["evaluation_deadline"]))
    lag = int(job.get("max_terminal_lag_seconds", _TIMEFRAME_SECONDS.get(str(job["timeframe"]), 0)))
    end = deadline + timedelta(seconds=lag)
    bars = adapter.closed_bars_between(job["symbol"], job["timeframe"], start, end)
    tick_error = None
    try:
        ticks = adapter.ticks_between(job["symbol"], start, end)
    except Exception as exc:  # Tick evidence is supplemental and never blocks Core bar collection.
        ticks = []
        tick_error = type(exc).__name__
    selected = eligible_bars(job, bars)
    prices = reconstruct_prices(selected, point=job["source_binding"].get("point"), ticks=ticks)
    source_binding = deepcopy(job["source_binding"])
    evidence_for_qc = {"source_binding": source_binding}
    qc = cross_snapshot_qc(job["source_binding"], evidence_for_qc)
    terminal = select_terminal_bar(job, selected)
    if terminal["status"] != "PASS":
        qc["status"] = "FAIL"
        qc["reasons"] = sorted(set(qc["reasons"] + [terminal["reason"]]))

    bundle = Path(output_root) / str(job["job_id"])
    bundle.mkdir(parents=True, exist_ok=True)
    bars_hash = _atomic_json(bundle / "bars.json", prices["bars"])
    ticks_hash = _atomic_json(bundle / "ticks.json", prices["ticks"])
    manifest = {
        "job_id": job["job_id"], "decision_id": job["decision_id"],
        "horizon": job["horizon"], "source_binding": source_binding,
        "qc": qc, "price_quality": prices["price_quality"],
        "tick_collection_error": tick_error,
        "raw_hashes": {"bars.json": bars_hash, "ticks.json": ticks_hash},
        "safety": deepcopy(job["safety"]),
    }
    manifest_hash = _atomic_json(bundle / "manifest.json", manifest)
    return {
        "evidence_id": stable_id("FOLLOWUP_EVIDENCE", job["job_id"], manifest_hash),
        "decision_id": job["decision_id"], "job_id": job["job_id"],
        "horizon": job["horizon"], "symbol": job["symbol"],
        "source_binding": source_binding, "bars": prices["bars"], "ticks": prices["ticks"],
        "terminal": terminal, "qc": qc, "price_quality": prices["price_quality"],
        "manifest_hash": manifest_hash,
        "evidence_refs": [str(bundle / "bars.json"), str(bundle / "ticks.json"), str(bundle / "manifest.json")],
        "safety": deepcopy(job["safety"]),
    }
