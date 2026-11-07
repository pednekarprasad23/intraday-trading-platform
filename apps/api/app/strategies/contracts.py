"""Frozen, broker-independent strategy inputs and outcomes (contract v1)."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class Candle:
    bar_time: datetime  # UTC interval opening, not yet observable at this instant
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None

    def __post_init__(self):
        if self.bar_time.tzinfo is None or self.bar_time.utcoffset() is None:
            raise ValueError("Candle time must be aware")
        if self.bar_time.utcoffset() != timedelta(0):
            raise ValueError("Candle time must be UTC")
        prices = (self.open, self.high, self.low, self.close)
        if any(
            not isinstance(p, Decimal) or not p.is_finite() or p <= 0 for p in prices
        ):
            raise ValueError("Finite positive Decimal prices required")
        if self.low > min(self.open, self.close) or self.high < max(
            self.open, self.close
        ):
            raise ValueError("Invalid OHLC")
        if self.volume is not None and (
            not isinstance(self.volume, Decimal)
            or not self.volume.is_finite()
            or self.volume < 0
        ):
            raise ValueError("Invalid volume")


@dataclass(frozen=True)
class Source:
    instrument_id: UUID
    provider: str
    provider_key: str
    partition_id: UUID
    partition_sha256: str
    source_sha256: str
    session_date: date
    timeframe: str
    expiry_date: date
    option_type: str


@dataclass(frozen=True)
class StrategyConfig:
    strategy_id: str
    version: int
    fast_period: int
    slow_period: int
    rsi_period: int
    rsi_floor: Decimal
    rsi_ceiling: Decimal


@dataclass(frozen=True)
class Decision:
    contract_version: int
    config: StrategyConfig
    source: Source
    window: tuple[Candle, ...]
    required_bars: int
    decision_time: datetime | None
    direction: str  # LONG or NONE; never an order
    quality: str  # VALID or REJECTED
    reasons: tuple[str, ...]
    fast_ema: Decimal | None = None
    slow_ema: Decimal | None = None
    rsi: Decimal | None = None


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Aware datetime required")
    return value.astimezone(timezone.utc)
