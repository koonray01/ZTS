from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

from .qc import validate_snapshot_qc
from .utils import REQUIRED_TIMEFRAMES, TIMEFRAME_MINUTES, iso_z, sanitize_id, utc_now


class SnapshotUnavailable(RuntimeError):
    pass


class SnapshotAdapter(ABC):
    source: str

    @abstractmethod
    def capture(self, *, symbol: str, run_id: str, bars: int = 60, include_h4: bool = True) -> dict[str, Any]:
        raise NotImplementedError


def _mask_account(login: Any) -> str | None:
    if login is None:
        return None
    text = str(login)
    if len(text) <= 4:
        return "*" * len(text)
    return f"{'*' * (len(text) - 4)}{text[-4:]}"


def _bar_id(symbol: str, timeframe: str, close_time: datetime) -> str:
    return sanitize_id(f"BAR_{symbol}_{timeframe}_{close_time.strftime('%Y%m%dT%H%M%SZ')}")


class FixtureSnapshotAdapter(SnapshotAdapter):
    source = "FIXTURE"

    def __init__(self, *, capture_time: datetime | None = None):
        self.capture_time = capture_time or datetime(2025, 3, 10, 12, 0, 10, tzinfo=timezone.utc)

    def capture(self, *, symbol: str, run_id: str, bars: int = 60, include_h4: bool = True) -> dict[str, Any]:
        request_id = sanitize_id(f"REQ_{run_id}_FIXTURE")
        snapshot_id = sanitize_id(f"SNAP_{run_id}_FIXTURE_{self.capture_time.strftime('%Y%m%dT%H%M%SZ')}")
        frames = list(REQUIRED_TIMEFRAMES) + (["H4"] if include_h4 else [])
        timeframes = []
        for tf in frames:
            minutes = TIMEFRAME_MINUTES[tf]
            last_close = self.capture_time.replace(second=0, microsecond=0)
            offset = last_close.minute % minutes
            if offset:
                last_close -= timedelta(minutes=offset)
            if last_close >= self.capture_time:
                last_close -= timedelta(minutes=minutes)
            frame_bars = []
            start = last_close - timedelta(minutes=minutes * bars)
            for index in range(bars):
                open_time = start + timedelta(minutes=minutes * index)
                close_time = open_time + timedelta(minutes=minutes)
                base = 2000.0 + index * 0.8 + (0.1 * len(tf))
                high = base + 1.4
                low = base - 1.1
                close = base + (0.4 if index % 2 == 0 else -0.2)
                frame_bars.append(
                    {
                        "bar_id": _bar_id(symbol, tf, close_time),
                        "open_time": iso_z(open_time),
                        "close_time": iso_z(close_time),
                        "open": round(base, 3),
                        "high": round(high, 3),
                        "low": round(low, 3),
                        "close": round(close, 3),
                        "tick_volume": 100 + index,
                        "real_volume": None,
                        "spread_points": 20,
                        "is_closed": True,
                    }
                )
            timeframes.append(
                {
                    "timeframe": tf,
                    "requested_bars": bars,
                    "returned_bars": len(frame_bars),
                    "last_closed_bar_time": frame_bars[-1]["close_time"],
                    "bars": frame_bars,
                }
            )
        snapshot = {
            "schema_version": "0.2.0",
            "snapshot_id": snapshot_id,
            "run_id": run_id,
            "request_id": request_id,
            "source": self.source,
            "symbol": symbol,
            "terminal": {
                "terminal_id": "FIXTURE-TERMINAL",
                "account_id": None,
                "server": None,
                "connected": False,
                "trade_write_enabled": False,
                "terminal_build": None,
            },
            "capture_time": iso_z(self.capture_time),
            "broker_time": iso_z(self.capture_time),
            "broker_utc_offset_minutes": 0,
            "last_tick_time": iso_z(self.capture_time - timedelta(seconds=1)),
            "freshness": {"status": "FRESH", "age_ms": 0, "stale_after_ms": 300000, "reasons": []},
            "timeframes": timeframes,
            "account_context": {"status": "UNAVAILABLE", "currency": None, "balance": None, "equity": None, "margin_free": None, "positions": []},
            "indicator_evidence": [],
            "evidence_refs": [sanitize_id(f"EVID_{snapshot_id}")],
            "qc": {"decision": "PASS", "checks": [], "warnings": [], "errors": []},
            "component_versions": {"snapshot_service": "ctl-mt5-snapshot-fixture-0.1.0"},
        }
        snapshot.update(validate_snapshot_qc(snapshot, now=self.capture_time))
        return snapshot


class MetaTrader5SnapshotAdapter(SnapshotAdapter):
    source = "LIVE_MT5"

    def __init__(self, mt5_module: Any | None = None):
        if mt5_module is None:
            try:
                import MetaTrader5 as mt5_module  # type: ignore
            except ImportError as exc:
                raise SnapshotUnavailable("MetaTrader5 package is not installed.") from exc
        self.mt5 = mt5_module

    def _tf(self, name: str) -> int:
        attr = f"TIMEFRAME_{name}"
        if not hasattr(self.mt5, attr):
            raise SnapshotUnavailable(f"MetaTrader5 timeframe is unavailable: {name}")
        return getattr(self.mt5, attr)

    def capture(self, *, symbol: str, run_id: str, bars: int = 60, include_h4: bool = True) -> dict[str, Any]:
        mt5 = self.mt5
        if not mt5.initialize():
            raise SnapshotUnavailable(f"MetaTrader5 terminal initialization failed: {mt5.last_error()}")
        try:
            if not mt5.symbol_select(symbol, True):
                raise SnapshotUnavailable(f"Symbol is unavailable or cannot be synchronized: {symbol}")
            terminal = mt5.terminal_info()
            account = mt5.account_info()
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                raise SnapshotUnavailable(f"No tick is available for symbol: {symbol}")
            capture = utc_now()
            broker_time = datetime.fromtimestamp(int(tick.time), tz=timezone.utc)
            frames = list(REQUIRED_TIMEFRAMES) + (["H4"] if include_h4 else [])
            timeframes = []
            for tf in frames:
                rates = mt5.copy_rates_from_pos(symbol, self._tf(tf), 1, bars)
                if rates is None or len(rates) == 0:
                    raise SnapshotUnavailable(f"No closed bars returned for {symbol} {tf}: {mt5.last_error()}")
                frame_bars = []
                minutes = TIMEFRAME_MINUTES[tf]
                for row in rates:
                    open_time = datetime.fromtimestamp(int(row["time"]), tz=timezone.utc)
                    close_time = open_time + timedelta(minutes=minutes)
                    frame_bars.append(
                        {
                            "bar_id": _bar_id(symbol, tf, close_time),
                            "open_time": iso_z(open_time),
                            "close_time": iso_z(close_time),
                            "open": float(row["open"]),
                            "high": float(row["high"]),
                            "low": float(row["low"]),
                            "close": float(row["close"]),
                            "tick_volume": int(row["tick_volume"]),
                            "real_volume": int(row["real_volume"]) if "real_volume" in row.dtype.names else None,
                            "spread_points": int(row["spread"]) if "spread" in row.dtype.names else None,
                            "is_closed": True,
                        }
                    )
                timeframes.append({"timeframe": tf, "requested_bars": bars, "returned_bars": len(frame_bars), "last_closed_bar_time": frame_bars[-1]["close_time"], "bars": frame_bars})
            positions = []
            raw_positions = mt5.positions_get(symbol=symbol) or []
            for pos in raw_positions:
                side = "BUY" if int(pos.type) == 0 else "SELL"
                positions.append({"position_id": str(pos.ticket), "symbol": pos.symbol, "side": side, "volume": float(pos.volume), "open_price": float(pos.price_open), "stop_loss": float(pos.sl) if pos.sl else None, "take_profit": float(pos.tp) if pos.tp else None, "open_time": iso_z(datetime.fromtimestamp(int(pos.time), tz=timezone.utc))})
            snapshot_id = sanitize_id(f"SNAP_{run_id}_{symbol}_{capture.strftime('%Y%m%dT%H%M%SZ')}")
            snapshot = {
                "schema_version": "0.2.0",
                "snapshot_id": snapshot_id,
                "run_id": run_id,
                "request_id": sanitize_id(f"REQ_{run_id}_{symbol}"),
                "source": self.source,
                "symbol": symbol,
                "terminal": {
                    "terminal_id": str(getattr(terminal, "name", "MT5-TERMINAL")),
                    "account_id": _mask_account(getattr(account, "login", None)),
                    "server": getattr(account, "server", None),
                    "connected": bool(getattr(terminal, "connected", False)),
                    "trade_write_enabled": False,
                    "terminal_build": getattr(terminal, "build", None),
                },
                "capture_time": iso_z(capture),
                "broker_time": iso_z(broker_time),
                "broker_utc_offset_minutes": int((broker_time - capture).total_seconds() // 60),
                "last_tick_time": iso_z(broker_time),
                "freshness": {"status": "FRESH", "age_ms": 0, "stale_after_ms": 300000, "reasons": []},
                "timeframes": timeframes,
                "account_context": {"status": "AVAILABLE" if account else "UNAVAILABLE", "currency": getattr(account, "currency", None), "balance": getattr(account, "balance", None), "equity": getattr(account, "equity", None), "margin_free": getattr(account, "margin_free", None), "positions": positions},
                "indicator_evidence": [],
                "evidence_refs": [sanitize_id(f"EVID_{snapshot_id}")],
                "qc": {"decision": "PASS", "checks": [], "warnings": [], "errors": []},
                "component_versions": {"snapshot_service": "ctl-mt5-snapshot-live-0.1.0"},
            }
            snapshot.update(validate_snapshot_qc(snapshot, now=capture))
            return snapshot
        finally:
            mt5.shutdown()
