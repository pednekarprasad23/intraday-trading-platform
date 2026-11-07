"""Read-only, allow-listed Windows MT5 operations. No trading functions are exposed."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol


class Terminal(Protocol):
    def initialize(self, **kwargs) -> bool: ...
    def shutdown(self) -> None: ...
    def terminal_info(self): ...
    def account_info(self): ...
    def positions_get(self): ...
    def history_deals_get(self, start, end): ...
    def symbol_info(self, symbol: str): ...
    def symbol_info_tick(self, symbol: str): ...


def decimal_string(value):
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Non-finite terminal value")
    return str(number)


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


@dataclass(frozen=True)
class Tick:
    symbol: str
    event_time: str
    received_at: str
    bid: str
    ask: str
    provenance: str = "MT5_TERMINAL"


class TerminalUnavailable(Exception):
    pass


class ReadOnlyBridge:
    def __init__(self, terminal: Terminal, terminal_path: str | None = None):
        self.terminal = terminal
        self.terminal_path = terminal_path
        self.initialized = False

    def connect(self) -> bool:
        kwargs = (
            {"path": self.terminal_path, "timeout": 5000}
            if self.terminal_path
            else {"timeout": 5000}
        )
        self.initialized = bool(self.terminal.initialize(**kwargs))
        return self.initialized

    def status(self) -> dict:
        info = self.terminal.terminal_info() if self.initialized else None
        return {
            "connected": bool(info and info.connected),
            "orders_available": False,
            "provenance": "MT5_TERMINAL",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _require_connected(self):
        if not self.status()["connected"]:
            raise TerminalUnavailable("MT5 terminal is disconnected")

    def account(self) -> dict:
        self._require_connected()
        info = self.terminal.account_info()
        if info is None:
            raise TerminalUnavailable("MT5 account unavailable")
        # Do not transmit login, name, server, company, or other identity fields.
        return {
            "currency": str(info.currency),
            "balance": decimal_string(info.balance),
            "equity": decimal_string(info.equity),
            "profit": decimal_string(info.profit),
            "margin": decimal_string(info.margin),
            "free_margin": decimal_string(info.margin_free),
            "provenance": "MT5_TERMINAL",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }

    def positions(self) -> list[dict]:
        self._require_connected()
        positions = self.terminal.positions_get()
        if positions is None:
            raise TerminalUnavailable("MT5 positions unavailable")
        return [
            {
                "symbol": str(p.symbol),
                "side": "BUY" if p.type == 0 else "SELL" if p.type == 1 else "UNKNOWN",
                "volume": decimal_string(p.volume),
                "price_open": decimal_string(p.price_open),
                "price_current": decimal_string(p.price_current),
                "profit": decimal_string(p.profit),
                "opened_at": timestamp(p.time),
            }
            for p in positions
        ]

    def history(self, days: int = 7) -> list[dict]:
        if not 1 <= days <= 30:
            raise ValueError("History window must be 1 to 30 days")
        self._require_connected()
        end = datetime.now(timezone.utc)
        deals = self.terminal.history_deals_get(end - timedelta(days=days), end)
        if deals is None:
            raise TerminalUnavailable("MT5 history unavailable")
        if len(deals) > 1000:
            raise TerminalUnavailable("Too many deals; choose a shorter window")
        return [
            {
                "symbol": str(d.symbol),
                "type": int(d.type),
                "volume": decimal_string(d.volume),
                "price": decimal_string(d.price),
                "profit": decimal_string(d.profit),
                "time": timestamp(d.time),
            }
            for d in deals
        ]

    def quote(self, symbol: str) -> Tick | None:
        self._require_connected()
        if not symbol or len(symbol) > 64:
            raise ValueError("Invalid symbol")
        if self.terminal.symbol_info(symbol) is None:
            return None
        tick = self.terminal.symbol_info_tick(symbol)
        if tick is None or not getattr(tick, "time_msc", None):
            return None
        bid, ask = Decimal(str(tick.bid)), Decimal(str(tick.ask))
        if not bid.is_finite() or not ask.is_finite() or bid <= 0 or ask <= 0:
            return None
        return Tick(
            symbol,
            datetime.fromtimestamp(tick.time_msc / 1000, timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
            str(bid),
            str(ask),
        )

    def close(self) -> None:
        if self.initialized:
            self.terminal.shutdown()
        self.initialized = False
