"""Universal Market Discovery Variable Foundation — V2.9A.

Provides generic variable/model foundation for markets, exchanges, asset classes,
instrument types, universes, underlyings, contracts, timeframes, and normalized
independent canonical identity generation.

Strictly decoupled from execution and trading modules.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Numeric,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Market(StrEnum):
    INDIA = "INDIA"


class Exchange(StrEnum):
    NSE = "NSE"
    NFO = "NFO"
    BSE = "BSE"
    MCX = "MCX"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"


class AssetClass(StrEnum):
    INDEX = "INDEX"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"


class InstrumentType(StrEnum):
    SPOT = "SPOT"
    INDEX = "INDEX"
    EQUITY = "EQUITY"
    OPTION = "OPTION"
    FUTURE = "FUTURE"


class OptionType(StrEnum):
    CALL = "CALL"
    PUT = "PUT"


class Timeframe(StrEnum):
    TF_1M = "1m"
    TF_3M = "3m"
    TF_5M = "5m"
    TF_15M = "15m"
    TF_30M = "30m"
    TF_1H = "1h"
    TF_1D = "1d"


class MarketUniverse(Base):
    """Generic MarketUniverse describing eligible discovery/scanning scope.

    Completely independent of execution and trading modules.
    """

    __tablename__ = "market_universes"
    __table_args__ = (
        UniqueConstraint("name", name="uq_market_universe_name"),
        CheckConstraint(
            "asset_class IN ('INDEX', 'EQUITY', 'COMMODITY', 'FOREX', 'CRYPTO')",
            name="ck_universe_asset_class",
        ),
        CheckConstraint(
            "instrument_type IN ('SPOT', 'INDEX', 'EQUITY', 'OPTION', 'FUTURE')",
            name="ck_universe_instrument_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    market: Mapped[str] = mapped_column(String(50), default=Market.INDIA)
    exchange: Mapped[str] = mapped_column(String(50), default=Exchange.NSE)
    asset_class: Mapped[str] = mapped_column(String(30), default=AssetClass.INDEX)
    instrument_type: Mapped[str] = mapped_column(String(30), default=InstrumentType.OPTION)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    underlying: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), default="DEMO")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    universe_metadata: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


def generate_canonical_identity(
    market: str,
    exchange: str,
    underlying: str,
    instrument_type: str,
    expiry: date | str | None = None,
    strike: Decimal | float | int | None = None,
    option_type: str | None = None,
) -> str:
    """Generate a stable, independent canonical normalized identity.

    Format: MARKET:EXCHANGE:UNDERLYING:INSTRUMENT_TYPE[:EXPIRY:STRIKE:OPTION_TYPE]
    """
    parts = [market.upper(), exchange.upper(), underlying.upper(), instrument_type.upper()]
    if instrument_type.upper() in (InstrumentType.OPTION.value, InstrumentType.FUTURE.value):
        if expiry:
            parts.append(str(expiry))
        if strike is not None:
            parts.append(str(Decimal(str(strike))))
        if option_type:
            parts.append(option_type.upper())
    return ":".join(parts)


class MarketCandidateModel(Base):
    """Durable database storage for MarketCandidate discovery evidence."""

    __tablename__ = "market_candidates"
    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_market_candidate_id"),
        Index("ix_market_candidates_scanner", "scanner_id"),
        Index("ix_market_candidates_contract", "canonical_contract_id"),
        Index("ix_market_candidates_detected", "detected_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    scanner_id: Mapped[str] = mapped_column(String(100), nullable=False)
    scanner_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    market: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(30), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(30), nullable=False)
    underlying: Mapped[str] = mapped_column(String(100), nullable=False)
    canonical_contract_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expiry: Mapped[str | None] = mapped_column(String(20), nullable=True)
    strike: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    option_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    discovery_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
