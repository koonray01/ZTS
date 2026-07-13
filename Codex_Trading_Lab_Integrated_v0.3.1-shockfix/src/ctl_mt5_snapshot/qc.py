from __future__ import annotations

from datetime import timedelta
from typing import Any

from .utils import REQUIRED_TIMEFRAMES, TIMEFRAME_MINUTES, parse_time


def _check(status: str, check_id: str, message: str) -> dict[str, str]:
    return {"check_id": check_id, "status": status, "message": message}


def _is_market_closure_gap(previous_close, close_time) -> bool:
    # FX/CFD feeds commonly omit weekend bars. This is not a missing live bar.
    cursor = previous_close
    while cursor < close_time:
        if cursor.weekday() in {5, 6}:
            return True
        # Common daily CFD/metals maintenance break around 21:00-22:00 UTC.
        if cursor.hour in {21, 22}:
            return True
        cursor += timedelta(hours=1)
    return previous_close.weekday() == 4 and close_time.weekday() == 0


def validate_snapshot_qc(snapshot: dict[str, Any], *, now=None, stale_after_ms: int | None = None) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    warnings: list[str] = []
    errors: list[str] = []
    frame_items = snapshot.get("timeframes", [])
    timeframes = {item["timeframe"]: item for item in frame_items}

    if len(timeframes) != len(frame_items):
        errors.append("Duplicate timeframe entries are not allowed.")
        checks.append(_check("FAIL", "QC_DUPLICATE_TIMEFRAME", errors[-1]))
    else:
        checks.append(_check("PASS", "QC_DUPLICATE_TIMEFRAME", "Each timeframe appears once."))

    if snapshot.get("source") == "LIVE_MT5":
        if not snapshot.get("terminal", {}).get("connected"):
            errors.append("LIVE_MT5 terminal is not connected.")
            checks.append(_check("FAIL", "QC_TERMINAL_CONNECTED", errors[-1]))
        else:
            checks.append(_check("PASS", "QC_TERMINAL_CONNECTED", "LIVE_MT5 terminal is connected."))

    missing = [tf for tf in REQUIRED_TIMEFRAMES if tf not in timeframes]
    if missing:
        errors.append("Missing required timeframes: " + ",".join(missing))
        checks.append(_check("FAIL", "QC_REQUIRED_TIMEFRAMES", errors[-1]))
    else:
        checks.append(_check("PASS", "QC_REQUIRED_TIMEFRAMES", "M5/M15/H1 are present."))

    capture = parse_time(snapshot["capture_time"])
    current = now or capture
    max_age = stale_after_ms or int(snapshot["freshness"]["stale_after_ms"])
    age_ms = max(0, int((current - capture).total_seconds() * 1000))
    if age_ms > max_age:
        errors.append(f"Snapshot is stale: {age_ms}ms > {max_age}ms")
        checks.append(_check("FAIL", "QC_FRESHNESS", errors[-1]))
    else:
        checks.append(_check("PASS", "QC_FRESHNESS", f"Snapshot age {age_ms}ms."))

    tick_time = snapshot.get("last_tick_time")
    if snapshot.get("source") == "LIVE_MT5":
        if not tick_time:
            errors.append("LIVE_MT5 snapshot has no last_tick_time.")
            checks.append(_check("FAIL", "QC_TICK_AGE", errors[-1]))
        else:
            tick_age_ms = max(0, int((capture - parse_time(tick_time)).total_seconds() * 1000))
            if tick_age_ms > max_age:
                errors.append(f"Live tick is stale: {tick_age_ms}ms > {max_age}ms")
                checks.append(_check("FAIL", "QC_TICK_AGE", errors[-1]))
            else:
                checks.append(_check("PASS", "QC_TICK_AGE", f"Live tick age {tick_age_ms}ms."))
        quote = snapshot.get("quote") or {}
        bid, ask = quote.get("bid"), quote.get("ask")
        if not isinstance(bid, (int, float)) or not isinstance(ask, (int, float)) or bid <= 0 or ask <= 0 or bid > ask:
            errors.append("LIVE_MT5 quote is missing or has invalid bid/ask.")
            checks.append(_check("FAIL", "QC_LIVE_QUOTE", errors[-1]))
        else:
            checks.append(_check("PASS", "QC_LIVE_QUOTE", "Live bid/ask quote is valid."))

    last_closes = []
    for tf, frame in timeframes.items():
        bars = frame.get("bars", [])
        minutes = TIMEFRAME_MINUTES[tf]
        if not bars:
            errors.append(f"{tf} has no bars.")
            checks.append(_check("FAIL", f"QC_{tf}_NONEMPTY", errors[-1]))
            continue
        if frame.get("returned_bars", 0) < frame.get("requested_bars", 0):
            errors.append(f"{tf} returned fewer bars than requested.")
            checks.append(_check("FAIL", f"QC_{tf}_COVERAGE", errors[-1]))
        else:
            checks.append(_check("PASS", f"QC_{tf}_COVERAGE", f"{tf} returned requested bar coverage."))
        if frame.get("returned_bars") != len(bars):
            errors.append(f"{tf} returned_bars does not match bars length.")
            checks.append(_check("FAIL", f"QC_{tf}_COUNT", errors[-1]))
        else:
            checks.append(_check("PASS", f"QC_{tf}_COUNT", f"{tf} has {len(bars)} bars."))
        maintenance_signatures: dict[int, int] = {}
        for previous, following in zip(bars, bars[1:]):
            previous_close = parse_time(previous["close_time"])
            close_time = parse_time(following["close_time"])
            if close_time - previous_close == timedelta(minutes=minutes * 2) and close_time.weekday() < 5:
                maintenance_signatures[close_time.hour] = maintenance_signatures.get(close_time.hour, 0) + 1

        seen_close = set()
        previous_close = None
        for index, bar in enumerate(bars):
            open_time = parse_time(bar["open_time"])
            close_time = parse_time(bar["close_time"])
            if not bar.get("is_closed"):
                errors.append(f"{tf} bar {bar.get('bar_id')} is not closed.")
            if close_time > capture:
                errors.append(f"{tf} bar {bar.get('bar_id')} closes after capture time.")
            if close_time in seen_close:
                errors.append(f"{tf} duplicate close_time {bar['close_time']}.")
            seen_close.add(close_time)
            if previous_close and close_time <= previous_close:
                errors.append(f"{tf} timestamps are not strictly increasing.")
            if previous_close and close_time - previous_close != timedelta(minutes=minutes):
                recurring_maintenance = (
                    close_time - previous_close == timedelta(minutes=minutes * 2)
                    and maintenance_signatures.get(close_time.hour, 0) >= 2
                )
                if _is_market_closure_gap(previous_close, close_time) or recurring_maintenance:
                    warnings.append(f"{tf} market-closure gap around {bar['close_time']}.")
                else:
                    errors.append(f"{tf} missing/gap around {bar['close_time']}.")
            if close_time - open_time != timedelta(minutes=minutes):
                errors.append(f"{tf} invalid bar duration at {bar.get('bar_id')}.")
            if not (bar["low"] <= bar["open"] <= bar["high"] and bar["low"] <= bar["close"] <= bar["high"]):
                errors.append(f"{tf} invalid OHLC at {bar.get('bar_id')}.")
            previous_close = close_time
            if index == len(bars) - 1:
                last_closes.append(close_time)
        if bars and frame["last_closed_bar_time"] != bars[-1]["close_time"]:
            errors.append(f"{tf} last_closed_bar_time does not match final bar.")

    retrieval_times = [parse_time(frame["retrieved_at"]) for frame in frame_items if frame.get("retrieved_at")]
    if len(retrieval_times) >= 2:
        retrieval_skew_ms = int((max(retrieval_times) - min(retrieval_times)).total_seconds() * 1000)
        if retrieval_skew_ms > 5_000:
            errors.append(f"Timeframe retrieval skew is too large: {retrieval_skew_ms}ms > 5000ms")
            checks.append(_check("FAIL", "QC_RETRIEVAL_SKEW", errors[-1]))
        else:
            checks.append(_check("PASS", "QC_RETRIEVAL_SKEW", f"Timeframe retrieval skew {retrieval_skew_ms}ms."))

    if len(last_closes) >= 2 and len(set(last_closes)) > 1:
        warnings.append("Timeframes have different last closed timestamps by design; cross-timeframe freshness remains checked.")
        checks.append(_check("WARN", "QC_MIXED_TIMEFRAME_CLOSES", warnings[-1]))
    else:
        checks.append(_check("PASS", "QC_MIXED_TIMEFRAME_CLOSES", "Last closed timestamps are aligned or single-frame."))

    deduped_errors = list(dict.fromkeys(errors))
    decision = "PASS" if not deduped_errors else "QUARANTINE"
    status = "FRESH" if not deduped_errors and age_ms <= max_age else "STALE" if age_ms > max_age else "BLOCKED"
    return {
        "freshness": {
            "status": status,
            "age_ms": age_ms,
            "stale_after_ms": max_age,
            "reasons": deduped_errors,
        },
        "qc": {
            "decision": decision,
            "checks": checks,
            "warnings": warnings,
            "errors": deduped_errors,
        },
    }
