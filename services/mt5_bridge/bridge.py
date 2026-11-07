"""Windows-host read-only MT5 facade. Does not expose order methods or a network listener."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol


class Terminal(Protocol):
    def initialize(self) -> bool: ...
    def shutdown(self) -> None: ...
    def terminal_info(self): ...
    def symbol_info(self, symbol: str): ...
    def symbol_info_tick(self, symbol: str): ...


@dataclass(frozen=True)
class Tick:
    symbol: str
    event_time: datetime
    received_at: datetime
    bid: Decimal
    ask: Decimal
    provenance: str = "MT5_TERMINAL"


class ReadOnlyBridge:
    def __init__(self, terminal: Terminal):
        self.terminal = terminal
        self.connected = False

    def connect(self) -> bool:
        self.connected = bool(self.terminal.initialize())
        return self.connected

    def status(self) -> dict:
        info = self.terminal.terminal_info() if self.connected else None
        return {
            "connected": bool(info),
            "orders_available": False,
            "python_runtime": "3.13-required",
        }

    def quote(self, symbol: str) -> Tick | None:
        if not self.connected or not symbol or len(symbol) > 64:
            return None
        if self.terminal.symbol_info(symbol) is None:
            return None
        tick = self.terminal.symbol_info_tick(symbol)
        if tick is None or not getattr(tick, "time_msc", None):
            return None
        bid, ask = Decimal(str(tick.bid)), Decimal(str(tick.ask))
        if not bid.is_finite() or not ask.is_finite() or bid <= 0 or ask <= 0:
            return None
        return Tick(symbol, datetime.fromtimestamp(tick.time_msc / 1000, timezone.utc), datetime.now(timezone.utc), bid, ask)

    def close(self) -> None:
        if self.connected:
            self.terminal.shutdown()
        self.connected = False
