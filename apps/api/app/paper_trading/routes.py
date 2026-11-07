"""Paper trading API routes — order submission, position management, kill switch, risk events."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth import require_user
from app.database import get_db
from app.models import Instrument
from app.paper_trading.engine import (
    PaperTradingEngine,
    reset_kill_switch as engine_reset_kill_switch,
    trigger_kill_switch as engine_trigger_kill_switch,
)
from app.paper_trading.models import (
    KillSwitch,
    KillSwitchState,
    PaperAccount,
    PaperFill,
    PaperOrder,
    PaperOrderSide,
    PaperOrderType,
    PaperPosition,
    PaperRiskEvent,
)

router = APIRouter(prefix="/api/v1/paper", dependencies=[Depends(require_user)])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class OrderRequest(BaseModel):
    """Request body for creating a paper order."""

    instrument_id: UUID = Field(description="Instrument to trade")
    side: str = Field(description="buy or sell", pattern="^(buy|sell)$")
    quantity: Decimal = Field(description="Quantity to trade", gt=0)
    order_type: str = Field(default="market", description="Order type", pattern="^(market|limit|stop|stop_limit)$")
    price: Decimal | None = Field(default=None, description="Limit price for limit orders")
    stop_price: Decimal | None = Field(default=None, description="Stop price for stop orders")
    strategy_id: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] | None = None


class OrderResponse(BaseModel):
    """Order response with execution details."""

    id: UUID
    account_id: UUID
    instrument_id: UUID
    side: str
    order_type: str
    quantity: Decimal
    filled_quantity: Decimal
    price: Decimal | None
    state: str
    created_at: datetime
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    rejected_reason: str | None = None
    fills: list[dict[str, Any]] = Field(default_factory=list)
    strategy_id: str | None = None


class PositionResponse(BaseModel):
    """Position response."""

    id: UUID
    account_id: UUID
    instrument_id: UUID
    symbol: str
    quantity: Decimal
    avg_entry_price: Decimal | None
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    last_marked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KillSwitchResponse(BaseModel):
    """Kill switch status."""

    name: str = "global"
    state: str = KillSwitchState.ARMED.value
    triggered_by: UUID | None = None
    triggered_at: datetime | None = None
    reason: str | None = None
    reset_by: UUID | None = None
    reset_at: datetime | None = None
    auto_triggered: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RiskEventResponse(BaseModel):
    """Risk event response."""

    id: UUID
    account_id: UUID
    event_type: str
    order_id: UUID | None = None
    instrument_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    blocked: bool
    created_at: datetime


class KillSwitchControl(BaseModel):
    """Kill switch control request."""

    reason: str = Field(..., max_length=500)


class PaginationResponse(BaseModel):
    """Pagination wrapper for responses."""

    total: int
    items: list[Any]


class AccountSummaryResponse(BaseModel):
    """Paper trading account summary with capital, positions, and P&L."""

    account_id: UUID
    name: str
    currency: str
    initial_capital: Decimal
    available_capital: Decimal
    reserved_capital: Decimal
    total_pnl: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    position_count: int
    open_position_value: Decimal


# ============================================================================
# Helper Functions
# ============================================================================


def get_active_account(db: Session) -> PaperAccount:
    """Get the first active paper account or raise 404."""
    account = db.scalar(select(PaperAccount).where(PaperAccount.is_active.is_(True)))
    if account is None:
        raise HTTPException(404, "No active paper trading account found")
    return account


def get_instrument(db: Session, instrument_id: UUID) -> Instrument:
    """Get instrument or raise 404."""
    instrument = db.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(404, f"Instrument {instrument_id} not found")
    return instrument


def serialize_fill(fill: PaperFill) -> dict[str, Any]:
    """Serialize a PaperFill to dict."""
    return {
        "id": str(fill.id),
        "order_id": str(fill.order_id),
        "quantity": str(fill.quantity),
        "price": str(fill.price),
        "commission": str(fill.commission),
        "fees": str(fill.fees),
        "slippage": str(fill.slippage),
        "filled_at": fill.filled_at,
        "provenance": fill.provenance,
    }


def parse_details(details_str: str | dict[str, Any]) -> dict[str, Any]:
    """Parse details from string or return dict."""
    if isinstance(details_str, dict):
        return details_str
    try:
        return json.loads(details_str) if isinstance(details_str, str) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


# ============================================================================
# Account Summary Endpoint
# ============================================================================


@router.get("/summary", response_model=AccountSummaryResponse)
def get_account_summary(
    db: Session = Depends(get_db),
):
    """Get paper trading account summary with capital, positions, and P&L."""
    account = get_active_account(db)

    positions = db.scalars(
        select(PaperPosition)
        .options(joinedload(PaperPosition.instrument))
        .where(PaperPosition.account_id == account.id)
    ).all()

    position_count = len(positions)
    open_position_value = sum(abs(pos.quantity) * (pos.avg_entry_price or Decimal(0)) for pos in positions)
    unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
    realized_pnl = sum(pos.realized_pnl for pos in positions)
    total_pnl = unrealized_pnl + realized_pnl
    reserved_capital = account.initial_capital - account.available_capital + total_pnl

    return AccountSummaryResponse(
        account_id=account.id,
        name=account.name,
        currency=account.currency,
        initial_capital=account.initial_capital,
        available_capital=account.available_capital,
        reserved_capital=reserved_capital,
        total_pnl=total_pnl,
        unrealized_pnl=unrealized_pnl,
        realized_pnl=realized_pnl,
        position_count=position_count,
        open_position_value=open_position_value,
    )


# ============================================================================
# Orders Endpoints
# ============================================================================


@router.post("/orders", response_model=OrderResponse, status_code=201)
def submit_order(
    body: OrderRequest,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Create and execute a paper order."""
    account = get_active_account(db)
    instrument = get_instrument(db, body.instrument_id)

    if not instrument.execution_enabled:
        raise HTTPException(400, "Instrument not enabled for execution")

    engine = PaperTradingEngine(db)
    result = engine.submit_order(
        account=account,
        instrument=instrument,
        side=PaperOrderSide(body.side),
        quantity=body.quantity,
        order_type=PaperOrderType(body.order_type),
        price=body.price,
        stop_price=body.stop_price,
        strategy_id=body.strategy_id,
    )

    order = result.order

    if not result.success and result.rejected_reason:
        reason_lower = result.rejected_reason.lower()
        if "loss" in reason_lower:
            event_type = "daily_loss_limit"
        elif "position" in reason_lower:
            event_type = "position_limit"
        elif "capital" in reason_lower:
            event_type = "insufficient_capital"
        else:
            event_type = "instrument_blocked"

        db.add(PaperRiskEvent(
            account_id=account.id,
            event_type=event_type,
            order_id=order.id,
            details={"reason": result.rejected_reason},
            blocked=True,
        ))

    db.commit()
    db.refresh(order)

    fills = [serialize_fill(f) for f in order.fills]

    return OrderResponse(
        id=order.id,
        account_id=order.account_id,
        instrument_id=order.instrument_id,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        filled_quantity=order.filled_quantity,
        price=order.price,
        state=order.state,
        created_at=order.created_at,
        submitted_at=order.submitted_at,
        filled_at=order.filled_at,
        rejected_reason=result.rejected_reason,
        fills=fills,
        strategy_id=order.strategy_id,
    )


@router.get("/orders", response_model=PaginationResponse)
def list_orders(
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List paper orders with optional filtering by state."""
    query = select(PaperOrder)

    if state:
        query = query.where(PaperOrder.state == state)

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    orders = db.scalars(
        query.order_by(PaperOrder.created_at.desc()).limit(limit).offset(offset)
    ).all()

    items = []
    for order in orders:
        fills = [serialize_fill(f) for f in order.fills]
        items.append(OrderResponse(
            id=order.id,
            account_id=order.account_id,
            instrument_id=order.instrument_id,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            price=order.price,
            state=order.state,
            created_at=order.created_at,
            submitted_at=order.submitted_at,
            filled_at=order.filled_at,
            rejected_reason=None,
            fills=fills,
            strategy_id=order.strategy_id,
        ))

    return PaginationResponse(total=total, items=items)


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: UUID, db: Session = Depends(get_db)):
    """Get detailed information about a specific order."""
    order = db.get(PaperOrder, order_id)
    if order is None:
        raise HTTPException(404, "Order not found")

    fills = [serialize_fill(f) for f in order.fills]

    rejection_reason = None
    try:
        meta = parse_details(order.order_metadata)
        rejection_reason = meta.get("rejection_reason")
    except Exception:
        pass

    return OrderResponse(
        id=order.id,
        account_id=order.account_id,
        instrument_id=order.instrument_id,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        filled_quantity=order.filled_quantity,
        price=order.price,
        state=order.state,
        created_at=order.created_at,
        submitted_at=order.submitted_at,
        filled_at=order.filled_at,
        rejected_reason=rejection_reason,
        fills=fills,
        strategy_id=order.strategy_id,
    )


# ============================================================================
# Positions Endpoints
# ============================================================================


@router.get("/positions", response_model=list[PositionResponse])
def list_positions(
    db: Session = Depends(get_db),
):
    """List all open positions for the default paper trading account."""
    account = get_active_account(db)

    positions = db.scalars(
        select(PaperPosition)
        .options(joinedload(PaperPosition.instrument))
        .where(PaperPosition.account_id == account.id)
        .where(PaperPosition.quantity != 0)
        .order_by(PaperPosition.instrument_id)
    ).all()

    items = []
    for pos in positions:
        items.append(PositionResponse(
            id=pos.id,
            account_id=pos.account_id,
            instrument_id=pos.instrument_id,
            symbol=pos.instrument.canonical_symbol if pos.instrument else "Unknown",
            quantity=pos.quantity,
            avg_entry_price=pos.avg_entry_price,
            unrealized_pnl=pos.unrealized_pnl,
            realized_pnl=pos.realized_pnl,
            last_marked_at=pos.last_marked_at,
            created_at=pos.created_at,
            updated_at=pos.updated_at,
        ))

    return items


# ============================================================================
# Kill Switch Endpoints
# ============================================================================


@router.post("/kill-switch", response_model=KillSwitchResponse, status_code=201)
def trigger_kill_switch_endpoint(
    body: KillSwitchControl,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Trigger the kill switch."""
    ks = engine_trigger_kill_switch(
        db=db,
        reason=body.reason,
        triggered_by=user.id,
        auto=False,
    )
    db.commit()

    return KillSwitchResponse(
        name=ks.name,
        state=ks.state,
        triggered_by=ks.triggered_by,
        triggered_at=ks.triggered_at,
        reason=ks.reason,
        reset_by=ks.reset_by,
        reset_at=ks.reset_at,
        auto_triggered=ks.auto_triggered,
        created_at=ks.created_at,
        updated_at=ks.updated_at,
    )


@router.post("/kill-switch/reset", response_model=KillSwitchResponse)
def reset_kill_switch_endpoint(
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Reset the kill switch after operator confirmation."""
    try:
        ks = db.scalar(select(KillSwitch).where(KillSwitch.name == "global"))
        if ks is None:
            raise HTTPException(404, "Kill switch not found")
        if ks.state != KillSwitchState.TRIGGERED:
            raise HTTPException(400, "Kill switch is not triggered")

        ks.state = KillSwitchState.RESET_PENDING
        ks.reset_by = user.id
        ks.reset_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(ks)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return KillSwitchResponse(
        name=ks.name,
        state=ks.state,
        triggered_by=ks.triggered_by,
        triggered_at=ks.triggered_at,
        reason=ks.reason,
        reset_by=ks.reset_by,
        reset_at=ks.reset_at,
        auto_triggered=ks.auto_triggered,
        created_at=ks.created_at,
        updated_at=ks.updated_at,
    )


@router.get("/kill-switch", response_model=KillSwitchResponse)
def get_kill_switch_status(
    db: Session = Depends(get_db),
):
    """Check the current kill switch status."""
    ks = db.scalar(select(KillSwitch).where(KillSwitch.name == "global"))

    if ks is None:
        now = datetime.now(timezone.utc)
        return KillSwitchResponse(
            name="global",
            state=KillSwitchState.ARMED.value,
            created_at=now,
            updated_at=now,
        )

    return KillSwitchResponse(
        name=ks.name,
        state=ks.state,
        triggered_by=ks.triggered_by,
        triggered_at=ks.triggered_at,
        reason=ks.reason,
        reset_by=ks.reset_by,
        reset_at=ks.reset_at,
        auto_triggered=ks.auto_triggered,
        created_at=ks.created_at,
        updated_at=ks.updated_at,
    )


# ============================================================================
# Risk Events Endpoints
# ============================================================================


@router.get("/risk-events", response_model=PaginationResponse)
def list_risk_events(
    event_type: str | None = None,
    blocked: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List recent risk events with optional filtering."""
    query = select(PaperRiskEvent)

    if event_type:
        query = query.where(PaperRiskEvent.event_type == event_type)
    if blocked is not None:
        query = query.where(PaperRiskEvent.blocked == blocked)

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    events = db.scalars(
        query.order_by(PaperRiskEvent.created_at.desc()).limit(limit).offset(offset)
    ).all()

    items = [
        RiskEventResponse(
            id=e.id,
            account_id=e.account_id,
            event_type=e.event_type,
            order_id=e.order_id,
            instrument_id=e.instrument_id,
            details=parse_details(e.details),
            blocked=e.blocked,
            created_at=e.created_at,
        )
        for e in events
    ]

    return PaginationResponse(total=total, items=items)


@router.get("/risk-events/{event_id}", response_model=RiskEventResponse)
def get_risk_event(event_id: UUID, db: Session = Depends(get_db)):
    """Get a specific risk event details."""
    event = db.get(PaperRiskEvent, event_id)
    if event is None:
        raise HTTPException(404, "Risk event not found")

    return RiskEventResponse(
        id=event.id,
        account_id=event.account_id,
        event_type=event.event_type,
        order_id=event.order_id,
        instrument_id=event.instrument_id,
        details=parse_details(event.details),
        blocked=event.blocked,
        created_at=event.created_at,
    )
