from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _decision_payload(path: Path) -> dict[str, Any]:
    payload = _load(path)
    return payload.get("payload", payload)


def _tf_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["timeframe"]: item for item in snapshot.get("timeframes", [])}


def _zones_by_tf(decision: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for zone in decision.get("market_packet", {}).get("active_zones", []):
        result.setdefault(zone.get("timeframe", "UNKNOWN"), []).append(zone)
    return result


def _zone_color(zone_type: str) -> str:
    upper = zone_type.upper()
    if any(token in upper for token in ("DEMAND", "SUPPORT")):
        return "#35b779"
    if any(token in upper for token in ("SUPPLY", "RESISTANCE")):
        return "#ef476f"
    if "FVG" in upper:
        return "#f4a261"
    return "#8e7dff"


def _plot_timeframe(ax: Any, tf: str, tf_data: dict[str, Any], zones: list[dict[str, Any]], location: dict[str, Any], bars: int) -> dict[str, Any]:
    candles = [item for item in tf_data.get("bars", []) if item.get("is_closed", True)][-bars:]
    if not candles:
        raise ValueError(f"No closed bars available for {tf}")
    times = [datetime.fromisoformat(item["open_time"].replace("Z", "+00:00")) for item in candles]
    width = (times[1] - times[0]).total_seconds() / 86400 * 0.72 if len(times) > 1 else 0.002
    for when, candle in zip(times, candles):
        x = mdates.date2num(when)
        opened, high, low, close = (float(candle[key]) for key in ("open", "high", "low", "close"))
        bullish = close >= opened
        color = "#00e676" if bullish else "#ff4d6d"
        ax.vlines(x, low, high, color=color, linewidth=0.8, zorder=3)
        ax.add_patch(Rectangle((x - width / 2, min(opened, close)), width, max(abs(close - opened), 0.01), facecolor=color, edgecolor=color, linewidth=0.6, zorder=4))

    visible_low = min(float(item["low"]) for item in candles)
    visible_high = max(float(item["high"]) for item in candles)
    for zone in zones:
        lower, upper = float(zone["lower"]), float(zone["upper"])
        if upper < visible_low or lower > visible_high:
            continue
        clipped_low, clipped_high = max(lower, visible_low), min(upper, visible_high)
        ax.axhspan(clipped_low, clipped_high, color=_zone_color(zone.get("zone_type", "")), alpha=0.12, zorder=0)
        ax.text(times[-1], (clipped_low + clipped_high) / 2, f" {zone.get('zone_type', 'ZONE')}", color=_zone_color(zone.get("zone_type", "")), fontsize=6, va="center", ha="left", alpha=0.9)

    structural = location.get("structural_reference_price")
    live_mid = location.get("live_mid")
    if structural is not None:
        ax.axhline(float(structural), color="#ffffff", linewidth=0.8, linestyle="--", alpha=0.8, label=f"struct {float(structural):.2f}")
    if live_mid is not None:
        ax.axhline(float(live_mid), color="#00b4d8", linewidth=0.9, linestyle="-", alpha=0.9, label=f"live {float(live_mid):.2f}")

    ax.set_title(tf, loc="left", color="white", fontsize=10, fontweight="bold")
    ax.grid(True, linestyle=":", linewidth=0.4, alpha=0.35)
    # Matplotlib 3.8/Python 3.14 can recurse while cloning tick markers on
    # dense multi-panel figures. Use explicit endpoint labels for a stable
    # diagnostic render instead of axis-managed ticks.
    ax.set_xticks([])
    ax.set_yticks([])
    ax.text(0.01, 0.02, times[0].strftime("%H:%M UTC"), transform=ax.transAxes, color="#bbbbbb", fontsize=6)
    ax.text(0.99, 0.02, times[-1].strftime("%H:%M UTC"), transform=ax.transAxes, color="#bbbbbb", fontsize=6, ha="right")
    ax.set_xlim(mdates.date2num(times[0]) - width, mdates.date2num(times[-1]) + width * 5)
    ax.set_ylim(visible_low - (visible_high - visible_low) * 0.06, visible_high + (visible_high - visible_low) * 0.06)
    return {"timeframe": tf, "bars_rendered": len(candles), "zones_rendered": sum(1 for zone in zones if not (float(zone["upper"]) < visible_low or float(zone["lower"]) > visible_high))}


def render(raw_snapshot: Path, decision_state: Path, output: Path, bars: int) -> dict[str, Any]:
    snapshot = _load(raw_snapshot)
    decision = _decision_payload(decision_state)
    tf_map = _tf_map(snapshot)
    ordered = [tf for tf in ("M5", "M15", "H1", "H4") if tf in tf_map]
    if not ordered:
        raise ValueError("Snapshot has no supported timeframe data")
    output.mkdir(parents=True, exist_ok=True)
    location = decision.get("market_packet", {}).get("location", {})
    states = {item.get("timeframe"): item for item in decision.get("market_packet", {}).get("market_state", [])}
    zones = _zones_by_tf(decision)

    fig, axes = plt.subplots(len(ordered), 1, figsize=(14, 3.5 * len(ordered)), sharex=False)
    if len(ordered) == 1:
        axes = [axes]
    fig.patch.set_facecolor("#0b0d10")
    summaries = []
    for ax, tf in zip(axes, ordered):
        ax.set_facecolor("#0b0d10")
        summary = _plot_timeframe(ax, tf, tf_map[tf], zones.get(tf, []), location, bars)
        state = states.get(tf, {})
        summary.update({key: state.get(key) for key in ("structure", "regime", "recent_leg", "phase", "volatility")})
        label = (
            f"structure={summary['structure']} | regime={summary['regime']} | "
            f"leg={summary['recent_leg']} | phase={summary['phase']} | volatility={summary['volatility']}"
        )
        ax.text(0.01, 0.96, label, transform=ax.transAxes, color="#ffd166", fontsize=7, va="top")
        summaries.append(summary)
    fig.suptitle(f"{snapshot.get('symbol', 'UNKNOWN')} | LIVE_MT5 | capture {snapshot.get('capture_time', '')}", color="white", fontsize=12)
    # Avoid tight_layout: large zone-label sets can trigger a matplotlib
    # artist deepcopy recursion on some Python/matplotlib combinations.
    fig.subplots_adjust(left=0.07, right=0.98, top=0.96, bottom=0.04, hspace=0.28)
    combined = output / "market_overview.png"
    fig.savefig(combined, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)

    return {
        "schema_version": "0.1.0",
        "source": snapshot.get("source"),
        "symbol": snapshot.get("symbol"),
        "snapshot_id": snapshot.get("snapshot_id"),
        "capture_time": snapshot.get("capture_time"),
        "quote": snapshot.get("quote"),
        "location": {key: location.get(key) for key in ("status", "structural_reference_price", "live_mid", "live_bid", "live_ask")},
        "market_state": summaries,
        "chart_state_summary_match": {
            "status": "PASS" if all(item.get("structure") is not None and item.get("phase") is not None and item.get("volatility") is not None for item in summaries) else "WARN",
            "reason": "Rendered labels use the same market_state projection as the textual action plan." if all(item.get("structure") is not None and item.get("phase") is not None and item.get("volatility") is not None for item in summaries) else "One or more rendered market-state fields are unavailable.",
        },
        "image": str(combined),
        "read_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a LIVE_MT5 OHLC snapshot with engine overlays; read-only QA.")
    parser.add_argument("--raw-snapshot", required=True, type=Path)
    parser.add_argument("--decision-state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bars", type=int, default=30)
    args = parser.parse_args()
    report = render(args.raw_snapshot, args.decision_state, args.output, args.bars)
    (args.output / "render_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
