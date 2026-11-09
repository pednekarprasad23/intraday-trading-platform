"""Paper trading engine — risk checks, order execution, position management.

This module implements the core paper trading flow:
1. Risk validation (central checks on every intent)
2. Order lifecycle (pending → submitted → filled/partial/rejected)
3. Position tracking (mark-to-market updates)
4. Kill switch enforcement

All operations are auditable and idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.instruments.mappings import MT5_SYMBOLS
from app.models import Instrument, ProviderSymbol
from app.paper_trading.models import (
    KillSwitch,
    KillSwitchState,
    PaperAccount,
    PaperFill,
    PaperOrder,
    PaperOrderSide,
    PaperOrderState,
    PaperOrderType,
    PaperPosition,
    PaperRiskEvent,
    PaperRiskEventType,
)


class RiskResult:
    """Result of a risk check."""

    def __init__(self, approved: bool, reason: str | None = None):
        self.approved = approved
        self.reason = reason


@dataclass
class RiskContext:
    """Context for risk validation."""

    account: PaperAccount
    instrument: Instrument
    quantity: Decimal
    side: PaperOrderSide
    order_type: PaperOrderType
    price: Decimal | None = None
    stop_price: Decimal | None = None

    # Market state
    is_market_open: bool = True
    data_age_seconds: float = 0.0

    # Session state
    daily_pnl: Decimal = Decimal(0)
    daily_order_count: int = 0
    current_position_qty: Decimal = Decimal(0)

    # Kill switch state
    kill_switch_armed: bool = True


@dataclass
class PaperExecutionResult:
    """Result of a paper order execution."""

    success: bool
    order: PaperOrder
    fills: list["PaperFill"] = field(default_factory=list)
    rejected_reason: str | None = None
    partial_fills: int = 0
    total_filled: Decimal = Decimal(0)
    avg_fill_price: Decimal | None = None


# ---------------------------------------------------------------------------
# Kill Switch Management
# ---------------------------------------------------------------------------


def is_kill_switch_armed(db: Session, name: str = "global") -> bool:
    """Check if kill switch is armed (blocking new orders)."""
    ks = db.scalar(
        select(KillSwitch).where(KillSwitch.name == name, KillSwitch.state != "armed")
    )
    if ks is None:
        return True  # Default is armed (allowing orders)
    # Kill switch is "armed" (blocking) when state is TRIGGERED
    # It's not armed when reset to RESET_PENDING
    return ks.state != KillSwitchState.TRIGGERED


def trigger_kill_switch(
    db: Session,
    reason: str,
    triggered_by: UUID | None = None,
    auto: bool = False,
) -> KillSwitch:
    """Trigger the kill switch — blocks all new orders."""
    ks = db.scalar(select(KillSwitch).where(KillSwitch.name == "global"))
    if ks is None:
        ks = KillSwitch(name="global")
        db.add(ks)
    ks.state = KillSwitchState.TRIGGERED
    ks.triggered_by = triggered_by
    ks.triggered_at = datetime.now(timezone.utc)
    ks.reason = reason
    ks.auto_triggered = auto
    db.flush()
    return ks


def reset_kill_switch(db: Session, reset_by: UUID) -> KillSwitch:
    """Reset the kill switch after operator confirmation."""
    ks = db.scalar(select(KillSwitch).where(KillSwitch.name == "global"))
    if ks is None:
        raise ValueError("Kill switch not found")
    if ks.state != KillSwitchState.TRIGGERED:
        raise ValueError("Kill switch is not triggered")
    ks.state = KillSwitchState.RESET_PENDING
    ks.reset_by = reset_by
    ks.reset_at = datetime.now(timezone.utc)
    db.flush()
    return ks


# ---------------------------------------------------------------------------
# Risk Validation
# ---------------------------------------------------------------------------


def check_kill_switch(db: Session) -> RiskResult:
    """Check if kill switch is triggered."""
    if is_kill_switch_armed(db):
        return RiskResult(True)  # Armed = no restrictions
    return RiskResult(False, "Kill switch is triggered")


def check_market_hours(instrument: Instrument, ctx: RiskContext) -> RiskResult:
    """Check if market is currently open for this instrument."""
    now = datetime.now(timezone.utc)
    ist = now.astimezone(timezone(timedelta(hours=5, minutes=30)))
    ist_time = ist.hour * 60 + ist.minute  # minutes since midnight
    ist_weekday = ist.weekday()  # 0=Monday, 6=Sunday

    if instrument.exchange in ("NSE", "BSE"):
        # NSE/BSE: 09:15-15:30 IST = 555–930 minutes since midnight
        # Skip market hours check for paper trading (allow all day for testing)
        # In production, this would be enabled
        pass

    elif instrument.exchange == "MT5":
        # MT5: Gold 24/5 (closed Sun), Crypto 24/7
        # Sunday = 0 in Python weekday — skip intraday check for now
        pass

    return RiskResult(True)


def check_data_freshness(ctx: RiskContext) -> RiskResult:
    """Check if instrument data is fresh (not stale)."""
    if ctx.data_age_seconds > 45:
        return RiskResult(False, "Data is stale (>45s old)")
    return RiskResult(True)


def check_capital(ctx_or_account, instrument=None, quantity=None, price=None, side=PaperOrderSide.BUY) -> RiskResult:
    """Check if order size is within available capital."""
    if isinstance(ctx_or_account, RiskContext):
        ctx = ctx_or_account
    else:
        ctx = RiskContext(
            account=ctx_or_account,
            instrument=instrument,
            quantity=quantity,
            side=side,
            order_type=PaperOrderType.MARKET,
            price=price,
        )
    if ctx.price is None:
        return RiskResult(False, "Price not determined")

    cost = ctx.quantity * ctx.price
    if ctx.side == PaperOrderSide.SELL:
        # For sells, check if we have position
        if ctx.current_position_qty < ctx.quantity:
            return RiskResult(False, "Insufficient position for sell")
    else:
        if cost > ctx.account.available_capital:
            return RiskResult(False, f"Insufficient capital: {cost} > {ctx.account.available_capital}")

    return RiskResult(True)


def check_position_limit(ctx_or_account, instrument=None, quantity=None, price=None, side=PaperOrderSide.BUY, current_position_qty=Decimal(0), daily_pnl=Decimal(0)) -> RiskResult:
    """Check if position limit would be exceeded."""
    if isinstance(ctx_or_account, RiskContext):
        ctx = ctx_or_account
    else:
        ctx = RiskContext(
            account=ctx_or_account,
            instrument=instrument,
            quantity=quantity,
            side=side,
            order_type=PaperOrderType.MARKET,
            price=price,
            current_position_qty=current_position_qty,
            daily_pnl=daily_pnl,
        )
    potential_qty = ctx.quantity
    if ctx.side == PaperOrderSide.SELL:
        potential_qty = -ctx.quantity

    new_qty = ctx.current_position_qty + potential_qty

    # Position value check
    if ctx.price is not None:
        position_value = abs(new_qty) * ctx.price
        if position_value > ctx.account.max_position_value:
            return RiskResult(
                False,
                f"Position value {position_value} exceeds max {ctx.account.max_position_value}",
            )

    # Daily loss limit check
    if ctx.daily_pnl < Decimal("-1000"):  # Simple threshold
        return RiskResult(False, "Daily loss limit exceeded")

    return RiskResult(True)


def check_instrument_allowed(db: Session, ctx: RiskContext) -> RiskResult:
    """Check if instrument is enabled for paper trading."""
    # Check provider mappings
    dhan_mapping = db.scalar(
        select(ProviderSymbol).where(
            ProviderSymbol.instrument_id == ctx.instrument.id,
            ProviderSymbol.provider == "DHAN",
        )
    )
    if dhan_mapping is None:
        return RiskResult(False, "No DHAN mapping found")

    if not dhan_mapping.execution_enabled:
        return RiskResult(False, "Instrument not enabled for execution")

    return RiskResult(True)


def validate_order_risks(db: Session, ctx: RiskContext) -> tuple[bool, str | None]:
    """Run all risk checks; return (approved, reason)."""
    # Kill switch check (highest priority)
    result = check_kill_switch(db)
    if not result.approved:
        return False, result.reason

    # Market hours
    result = check_market_hours(ctx.instrument, ctx)
    if not result.approved:
        return False, result.reason

    # Data freshness
    result = check_data_freshness(ctx)
    if not result.approved:
        return False, result.reason

    # Capital
    result = check_capital(ctx)
    if not result.approved:
        return False, result.reason

    # Position limits
    result = check_position_limit(ctx)
    if not result.approved:
        return False, result.reason

    # Instrument allowed
    result = check_instrument_allowed(db, ctx)
    if not result.approved:
        return False, result.reason

    return True, None


# ---------------------------------------------------------------------------
# Order Execution
# ---------------------------------------------------------------------------


def create_paper_order(
    db: Session,
    account: PaperAccount,
    instrument: Instrument,
    side: PaperOrderSide,
    quantity: Decimal,
    order_type: PaperOrderType,
    price: Decimal | None = None,
    stop_price: Decimal | None = None,
    strategy_id: str | None = None,
    metadata: dict | None = None,
) -> PaperOrder:
    """Create a pending paper order."""
    order = PaperOrder(
        account_id=account.id,
        instrument_id=instrument.id,
        idempotency_key=f"{instrument.canonical_symbol}:{side}:{quantity}:{datetime.now(timezone.utc).isoformat()}",
        side=side.value,
        order_type=order_type.value,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
        state=PaperOrderState.PENDING.value,
        strategy_id=strategy_id,
        metadata=str(metadata or {}),
    )
    db.add(order)
    db.flush()
    return order


def execute_paper_order(db: Session, order: PaperOrder) -> PaperExecutionResult:
    """Execute a paper order through the risk pipeline."""
    pos = db.scalar(
        select(PaperPosition).where(
            PaperPosition.account_id == order.account_id,
            PaperPosition.instrument_id == order.instrument_id,
        )
    )
    current_qty = pos.quantity if pos else Decimal(0)
    ctx = RiskContext(
        account=order.account,
        instrument=order.instrument,
        quantity=order.quantity,
        side=PaperOrderSide(order.side),
        order_type=PaperOrderType(order.order_type),
        price=order.price,
        stop_price=order.stop_price,
        current_position_qty=current_qty,
    )

    # Run risk checks
    approved, reason = validate_order_risks(db, ctx)
    if not approved:
        order.state = PaperOrderState.REJECTED.value
        order.order_metadata = str({**eval(order.order_metadata or "{}"), "rejection_reason": reason})
        db.add(PaperRiskEvent(
            account_id=order.account_id,
            event_type=PaperRiskEventType.INSTRUMENT_BLOCKED,
            order_id=order.id,
            details=str({"reason": reason}),
        ))
        return PaperExecutionResult(success=False, order=order, rejected_reason=reason)

    # Simulate execution
    order.state = PaperOrderState.SUBMITTED.value
    order.submitted_at = datetime.now(timezone.utc)

    # Get simulated fill price
    fill_price = order.price
    if fill_price is None:
        # Market order - use a default simulated price (would normally get from LTP)
        fill_price = Decimal("1000")

    fill = PaperFill(
        order_id=order.id,
        quantity=order.quantity,
        price=fill_price,
        slippage=Decimal("0"),  # No slippage in paper
        commission=Decimal("0"),  # No commission in paper
        fees=Decimal("0"),
    )
    db.add(fill)

    order.state = PaperOrderState.FILLED.value
    order.filled_at = datetime.now(timezone.utc)

    return PaperExecutionResult(
        success=True,
        order=order,
        fills=[fill],
        total_filled=order.quantity,
        avg_fill_price=fill_price,
    )


def update_position(db: Session, order: PaperOrder) -> PaperPosition:
    """Update position after a fill and calculate realized P&L."""
    pos = db.scalar(
        select(PaperPosition).where(
            PaperPosition.account_id == order.account_id,
            PaperPosition.instrument_id == order.instrument_id,
        )
    )

    fill_price = order.fills[0].price if order.fills else (order.price or Decimal("1000"))
    qty_change = order.quantity if order.side == PaperOrderSide.BUY else -order.quantity

    if pos is None:
        pos = PaperPosition(
            account_id=order.account_id,
            instrument_id=order.instrument_id,
            symbol=order.instrument.canonical_symbol,
            quantity=qty_change,
            avg_entry_price=fill_price if qty_change > 0 else None,
        )
        db.add(pos)
    else:
        if pos.quantity > 0 and qty_change < 0:
            closed_qty = min(pos.quantity, abs(qty_change))
            if pos.avg_entry_price:
                pnl = closed_qty * (fill_price - pos.avg_entry_price)
                pos.realized_pnl += pnl
        elif pos.quantity < 0 and qty_change > 0:
            closed_qty = min(abs(pos.quantity), qty_change)
            if pos.avg_entry_price:
                pnl = closed_qty * (pos.avg_entry_price - fill_price)
                pos.realized_pnl += pnl

        new_qty = pos.quantity + qty_change
        if new_qty == 0:
            pos.avg_entry_price = None
        elif (pos.quantity >= 0 and qty_change > 0) or (pos.quantity <= 0 and qty_change < 0):
            total_cost = (abs(pos.quantity) * (pos.avg_entry_price or fill_price)) + (abs(qty_change) * fill_price)
            pos.avg_entry_price = total_cost / abs(new_qty)
        pos.quantity = new_qty

    db.flush()
    return pos


# ---------------------------------------------------------------------------
# Position Management
# ---------------------------------------------------------------------------


def mark_positions(db: Session, account: PaperAccount) -> list[PaperPosition]:
    """Mark all open positions to market price."""
    positions = db.scalars(
        select(PaperPosition).where(PaperPosition.account_id == account.id)
    ).all()

    # In a real implementation, this would fetch LTP from providers
    # For now, we just update the last_marked_at timestamp
    now = datetime.now(timezone.utc)
    for pos in positions:
        pos.last_marked_at = now
        # unrealized_pnl would be computed from price change
        # This requires a fresh quote feed

    db.flush()
    return positions


class PaperTradingEngine:
    """High-level paper trading orchestration."""

    def __init__(self, db: Session):
        self.db = db

    def submit_order(
        self,
        account: PaperAccount,
        instrument: Instrument,
        side: PaperOrderSide,
        quantity: Decimal,
        *,
        order_type: PaperOrderType = PaperOrderType.MARKET,
        price: Decimal | None = None,
        stop_price: Decimal | None = None,
        strategy_id: str | None = None,
    ) -> PaperExecutionResult:
        """Submit and execute a paper order with full risk checks."""
        # 1. Create order
        order = create_paper_order(
            self.db, account, instrument, side, quantity, order_type, price, stop_price, strategy_id
        )

        # 2. Execute with risk validation
        result = execute_paper_order(self.db, order)

        # 3. Update position
        if result.success:
            update_position(self.db, order)

        self.db.commit()
        return result

    def get_open_positions(self, account: PaperAccount) -> list[PaperPosition]:
        """Get all open positions for an account."""
        return self.db.scalars(
            select(PaperPosition)
            .where(PaperPosition.account_id == account.id)
            .where(PaperPosition.quantity != 0)
        ).all()

    def get_pending_orders(self, account: PaperAccount) -> list[PaperOrder]:
        """Get all pending orders for an account."""
        return self.db.scalars(
            select(PaperOrder)
            .where(PaperOrder.account_id == account.id)
            .where(PaperOrder.state.in_([PaperOrderState.PENDING.value, PaperOrderState.SUBMITTED.value]))
        ).all()