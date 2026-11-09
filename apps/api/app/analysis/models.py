"""Historical Observation database model for V2.10A Replay Foundation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    JSON,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HistoricalObservationModel(Base):
    """Durable point-in-time historical market observation for exact replay."""

    __tablename__ = "historical_observations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    canonical_contract_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    market: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    underlying: Mapped[str] = mapped_column(String(100), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(50), nullable=False)
    expiry: Mapped[str | None] = mapped_column(String(50), nullable=True)
    strike: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    option_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    spot_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    open_interest: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bid_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    ask_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    # Optional fields preserving explicit NULL vs 0 distinction
    implied_volatility: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    delta: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    gamma: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    theta: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    vega: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)

    lot_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tick_size: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="fixture")
    provider_instrument_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    scanner_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    analysis_engine_versions: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("canonical_contract_id", "observed_at", name="uq_historical_observation_point_in_time"),
    )
