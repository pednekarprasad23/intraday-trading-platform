"""Paper trading models — separated ledger, orders, positions, risk limits, kill switch.

All paper trading is completely isolated from any broker account.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PaperAccount(Base):
    """Paper trading account — separate from any broker account."""

    __tablename__ = "paper_accounts"
    __table_args__ = (
        CheckConstraint("currency IN ('INR', 'USD')", name="ck_paper_currency"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    available_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    max_position_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    max_daily_loss: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    max_total_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    orders: Mapped[list["PaperOrder"]] = relationship(back_populates="account")
    positions: Mapped[list["PaperPosition"]] = relationship(back_populates="account")
    risk_events: Mapped[list["PaperRiskEvent"]] = relationship(back_populates="account")


class PaperOrderState(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    UNCERTAIN = "uncertain"  # broker response timeout / ambiguous


class PaperOrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class PaperOrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class PaperOrder(Base):
    """Paper order — fully auditable, idempotent lifecycle."""

    __tablename__ = "paper_orders"
    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="ck_paper_side"),
        CheckConstraint(
            "order_type IN ('market', 'limit', 'stop', 'stop_limit')",
            name="ck_paper_order_type",
        ),
        CheckConstraint(
            "state IN ('pending', 'submitted', 'filled', 'partial', 'rejected', 'cancelled', 'expired', 'uncertain')",
            name="ck_paper_state",
        ),
        UniqueConstraint("idempotency_key", name="uq_paper_idempotency"),
        Index("ix_paper_account_state", "account_id", "state"),
        Index("ix_paper_instrument_state", "instrument_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("paper_accounts.id", ondelete="CASCADE")
    )
    instrument_id: Mapped[UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str] = mapped_column(String(64))  # client-provided
    side: Mapped[str] = mapped_column(String(4))
    order_type: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    time_in_force: Mapped[str] = mapped_column(String(20), default="DAY")  # DAY, GTC, IOC, FOK
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("paper_orders.id"), nullable=True
    )
    strategy_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strategy_version: Mapped[int | None] = mapped_column(nullable=True)
    order_metadata: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["PaperAccount"] = relationship(back_populates="orders")
    instrument: Mapped["Instrument"] = relationship()
    fills: Mapped[list["PaperFill"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class PaperFill(Base):
    """Paper fill — immutable record of execution."""

    __tablename__ = "paper_fills"
    __table_args__ = (
        UniqueConstraint("order_id", "fill_sequence", name="uq_paper_fill_seq"),
        Index("ix_paper_fill_time", "filled_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("paper_orders.id", ondelete="CASCADE")
    )
    fill_sequence: Mapped[int] = mapped_column()
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    commission: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    slippage: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    provenance: Mapped[str] = mapped_column(String(50), default="PAPER_SIM")

    order: Mapped["PaperOrder"] = relationship(back_populates="fills")


class PaperPosition(Base):
    """Paper position — mark-to-market from stored prices."""

    __tablename__ = "paper_positions"
    __table_args__ = (
        UniqueConstraint("account_id", "instrument_id", name="uq_paper_position"),
        Index("ix_paper_position_account", "account_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("paper_accounts.id", ondelete="CASCADE")
    )
    instrument_id: Mapped[UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT")
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    avg_entry_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    last_marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    account: Mapped["PaperAccount"] = relationship(back_populates="positions")
    instrument: Mapped["Instrument"] = relationship()


class PaperRiskEventType(StrEnum):
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    POSITION_LIMIT = "position_limit"
    EXPOSURE_LIMIT = "exposure_limit"
    INSTRUMENT_BLOCKED = "instrument_blocked"
    KILL_SWITCH = "kill_switch"
    STALE_DATA = "stale_data"
    INSUFFICIENT_CAPITAL = "insufficient_capital"
    MAX_ORDERS_PER_SESSION = "max_orders_per_session"


class PaperRiskEvent(Base):
    """Risk check event — every blocked intent is recorded."""

    __tablename__ = "paper_risk_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('daily_loss_limit', 'position_limit', 'exposure_limit', 'instrument_blocked', 'kill_switch', 'stale_data', 'insufficient_capital', 'max_orders_per_session')",
            name="ck_paper_risk_type",
        ),
        Index("ix_paper_risk_account_time", "account_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("paper_accounts.id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String(40))
    order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("paper_orders.id"), nullable=True
    )
    instrument_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("instruments.id"), nullable=True
    )
    details: Mapped[str] = mapped_column(Text, default="{}")
    blocked: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    account: Mapped["PaperAccount"] = relationship(back_populates="risk_events")


class KillSwitchState(StrEnum):
    ARMED = "armed"  # normal operation
    TRIGGERED = "triggered"  # stop active, blocking new orders
    RESET_PENDING = "reset_pending"  # awaiting operator confirmation


class KillSwitch(Base):
    """Persistent server-side kill switch — survives restarts."""

    __tablename__ = "kill_switch"
    __table_args__ = (UniqueConstraint("name", name="uq_kill_switch"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), default="global")
    state: Mapped[str] = mapped_column(String(20), default="armed")
    triggered_by: Mapped[UUID | None] = mapped_column(nullable=True)  # user id
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reset_by: Mapped[UUID | None] = mapped_column(nullable=True)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )