"""Paper trading API routes — order submission, position management, kill switch, risk events, and paper signals."""

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
    PaperSignal,
)
from app.paper_trading.service import PaperExecutionService
from app.projects.models import Project, StrategyVersion

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


class FillResponse(BaseModel):
    id: UUID
    order_id: UUID
    quantity: Decimal
    price: Decimal
    commission: Decimal
    fees: Decimal
    slippage: Decimal
    filled_at: datetime
    provenance: str


class OrderResponse(BaseModel):
    id: UUID
    account_id: UUID
    instrument_id: UUID
    project_id: UUID | None = None
    strategy_version_id: UUID | None = None
    signal_id: UUID | None = None
    side: str
    order_type: str
    quantity: Decimal
    filled_quantity: Decimal
    price: Decimal | None
    state: str
    created_at: datetime
    submitted_at: datetime | None
    filled_at: datetime | None
    rejected_reason: str | None
    fills: list[FillResponse]
    strategy_id: str | None


class SignalSubmissionRequest(BaseModel):
    project_id: UUID = Field(description="Project ID generating signal")
    strategy_version_id: UUID = Field(description="Strategy Version ID")
    instrument_id: UUID = Field(description="Instrument ID")
    direction: str = Field(description="LONG or SHORT", pattern="^(LONG|SHORT)$")
    signal_type: str = Field(description="ENTRY or EXIT", pattern="^(ENTRY|EXIT)$")
    requested_quantity: Decimal = Field(description="Quantity requested", gt=0)
    correlation_id: str = Field(description="Unique correlation ID for idempotency", min_length=1, max_length=128)
    reference_price: Decimal | None = Field(default=None, description="Reference market price")
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None


class SignalResponse(BaseModel):
    id: UUID
    project_id: UUID
    strategy_version_id: UUID
    instrument_id: UUID
    direction: str
    signal_type: str
    requested_quantity: Decimal
    reference_price: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    status: str
    reason: str | None
    correlation_id: str
    created_at: datetime
    order: OrderResponse | None = None


class PaginationResponse(BaseModel):
    total: int
    items: list[Any]


# ============================================================================
# Helpers
# ============================================================================


def serialize_fill(f: PaperFill) -> FillResponse:
    return FillResponse(
        id=f.id,
        order_id=f.order_id,
        quantity=f.quantity,
        price=f.price,
        commission=f.commission,
        fees=f.fees,
        slippage=f.slippage,
        filled_at=f.filled_at,
        provenance=f.provenance,
    )


def serialize_order(o: PaperOrder) -> OrderResponse:
    fills = [serialize_fill(f) for f in o.fills]
    return OrderResponse(
        id=o.id,
        account_id=o.account_id,
        instrument_id=o.instrument_id,
        project_id=o.project_id,
        strategy_version_id=o.strategy_version_id,
        signal_id=o.signal_id,
        side=o.side,
        order_type=o.order_type,
        quantity=o.quantity,
        filled_quantity=o.filled_quantity,
        price=o.price,
        state=o.state,
        created_at=o.created_at,
        submitted_at=o.submitted_at,
        filled_at=o.filled_at,
        rejected_reason=None,
        fills=fills,
        strategy_id=o.strategy_id,
    )


# ============================================================================
# Paper Signal Endpoints
# ============================================================================


@router.get("/signals", response_model=PaginationResponse)
def list_signals(
    project_id: UUID | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List paper signals with optional filtering by project or status."""
    query = select(PaperSignal)
    if project_id:
        query = query.where(PaperSignal.project_id == project_id)
    if status:
        query = query.where(PaperSignal.status == status.upper())

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    signals = db.scalars(
        query.order_by(PaperSignal.created_at.desc()).limit(limit).offset(offset)
    ).all()

    items = []
    for sig in signals:
        order_resp = serialize_order(sig.order) if sig.order else None
        items.append(SignalResponse(
            id=sig.id,
            project_id=sig.project_id,
            strategy_version_id=sig.strategy_version_id,
            instrument_id=sig.instrument_id,
            direction=sig.direction,
            signal_type=sig.signal_type,
            requested_quantity=sig.requested_quantity,
            reference_price=sig.reference_price,
            stop_loss=sig.stop_loss,
            take_profit=sig.take_profit,
            status=sig.status,
            reason=sig.reason,
            correlation_id=sig.correlation_id,
            created_at=sig.created_at,
            order=order_resp,
        ))

    return PaginationResponse(total=total, items=items)


@router.get("/signals/{signal_id}", response_model=SignalResponse)
def get_signal(signal_id: UUID, db: Session = Depends(get_db)):
    """Get detailed traceability for a specific paper signal."""
    sig = db.get(PaperSignal, signal_id)
    if sig is None:
        raise HTTPException(404, f"Signal {signal_id} not found")

    order_resp = serialize_order(sig.order) if sig.order else None
    return SignalResponse(
        id=sig.id,
        project_id=sig.project_id,
        strategy_version_id=sig.strategy_version_id,
        instrument_id=sig.instrument_id,
        direction=sig.direction,
        signal_type=sig.signal_type,
        requested_quantity=sig.requested_quantity,
        reference_price=sig.reference_price,
        stop_loss=sig.stop_loss,
        take_profit=sig.take_profit,
        status=sig.status,
        reason=sig.reason,
        correlation_id=sig.correlation_id,
        created_at=sig.created_at,
        order=order_resp,
    )


@router.post("/test-signals", response_model=SignalResponse, status_code=201)
def submit_test_signal(
    body: SignalSubmissionRequest,
    db: Session = Depends(get_db),
):
    """Development/test endpoint to inject a deterministic paper signal through the execution service.

    Gated for paper infrastructure validation. Zero broker coupling.
    """
    project = db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(404, f"Project {body.project_id} not found")

    strategy_version = db.get(StrategyVersion, body.strategy_version_id)
    if strategy_version is None:
        raise HTTPException(404, f"StrategyVersion {body.strategy_version_id} not found")

    instrument = db.get(Instrument, body.instrument_id)
    if instrument is None:
        raise HTTPException(404, f"Instrument {body.instrument_id} not found")

    account = db.scalar(select(PaperAccount).where(PaperAccount.is_active == True))
    if account is None:
        raise HTTPException(400, "No active paper trading account found")

    signal, exec_result = PaperExecutionService.submit_signal(
        db=db,
        project=project,
        strategy_version=strategy_version,
        instrument=instrument,
        account=account,
        direction=body.direction,
        signal_type=body.signal_type,
        requested_quantity=body.requested_quantity,
        correlation_id=body.correlation_id,
        reference_price=body.reference_price,
        stop_loss=body.stop_loss,
        take_profit=body.take_profit,
    )

    order_resp = serialize_order(signal.order) if signal.order else None
    return SignalResponse(
        id=signal.id,
        project_id=signal.project_id,
        strategy_version_id=signal.strategy_version_id,
        instrument_id=signal.instrument_id,
        direction=signal.direction,
        signal_type=signal.signal_type,
        requested_quantity=signal.requested_quantity,
        reference_price=signal.reference_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        status=signal.status,
        reason=signal.reason,
        correlation_id=signal.correlation_id,
        created_at=signal.created_at,
        order=order_resp,
    )


# ============================================================================
# Existing Paper Trading Endpoints
# ============================================================================


@router.get("/summary")
def get_account_summary(db: Session = Depends(get_db)):
    """Get active paper account summary."""
    account = db.scalar(select(PaperAccount).where(PaperAccount.is_active == True))
    if account is None:
        raise HTTPException(404, "No active paper account found")

    positions = db.scalars(
        select(PaperPosition).where(PaperPosition.account_id == account.id)
    ).all()

    total_unrealized = sum((p.unrealized_pnl for p in positions), Decimal(0))
    total_realized = sum((p.realized_pnl for p in positions), Decimal(0))
    open_pos_value = sum((abs(p.quantity * (p.avg_entry_price or 0)) for p in positions), Decimal(0))

    return {
        "account_id": str(account.id),
        "name": account.name,
        "currency": account.currency,
        "initial_capital": str(account.initial_capital),
        "available_capital": str(account.available_capital),
        "reserved_capital": str(account.max_total_exposure),
        "total_pnl": str(total_unrealized + total_realized),
        "unrealized_pnl": str(total_unrealized),
        "realized_pnl": str(total_realized),
        "position_count": len(positions),
        "open_position_value": str(open_pos_value),
    }


@router.get("/positions")
def list_positions(db: Session = Depends(get_db)):
    """List open positions for the active paper account."""
    account = db.scalar(select(PaperAccount).where(PaperAccount.is_active == True))
    if account is None:
        raise HTTPException(404, "No active paper account found")

    positions = db.scalars(
        select(PaperPosition)
        .options(joinedload(PaperPosition.account))
        .where(PaperPosition.account_id == account.id)
    ).all()

    items = []
    for pos in positions:
        instrument = db.get(Instrument, pos.instrument_id)
        items.append({
            "id": str(pos.id),
            "account_id": str(pos.account_id),
            "instrument_id": str(pos.instrument_id),
            "symbol": instrument.canonical_symbol if instrument else "Unknown",
            "quantity": str(pos.quantity),
            "avg_entry_price": str(pos.avg_entry_price) if pos.avg_entry_price else None,
            "unrealized_pnl": str(pos.unrealized_pnl),
            "realized_pnl": str(pos.realized_pnl),
            "last_marked_at": pos.last_marked_at.isoformat() if pos.last_marked_at else None,
            "created_at": pos.created_at.isoformat(),
            "updated_at": pos.updated_at.isoformat(),
        })

    return items


@router.post("/orders", response_model=OrderResponse, status_code=201)
def submit_order(body: OrderRequest, db: Session = Depends(get_db)):
    """Submit a paper order (manual execution)."""
    account = db.scalar(select(PaperAccount).where(PaperAccount.is_active == True))
    if account is None:
        raise HTTPException(400, "No active paper trading account found")

    instrument = db.get(Instrument, body.instrument_id)
    if instrument is None:
        raise HTTPException(404, "Instrument not found")

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
            order_id=order.id if order else None,
            details={"reason": result.rejected_reason},
            blocked=True,
        ))

    db.commit()
    if order:
        db.refresh(order)
        return serialize_order(order)
    raise HTTPException(400, result.rejected_reason or "Order submission failed")


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

    items = [serialize_order(o) for o in orders]
    return PaginationResponse(total=total, items=items)


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: UUID, db: Session = Depends(get_db)):
    """Get detailed information about a specific order."""
    order = db.get(PaperOrder, order_id)
    if order is None:
        raise HTTPException(404, f"Order {order_id} not found")
    return serialize_order(order)


@router.get("/kill-switch")
def get_kill_switch_status(db: Session = Depends(get_db)):
    """Get global kill switch status."""
    ks = db.scalar(select(KillSwitch).where(KillSwitch.name == "global"))
    if ks is None:
        ks = KillSwitch(name="global", state=KillSwitchState.ARMED)
        db.add(ks)
        db.commit()
        db.refresh(ks)

    return {
        "name": ks.name,
        "state": ks.state,
        "triggered_by": ks.triggered_by,
        "triggered_at": ks.triggered_at.isoformat() if ks.triggered_at else None,
        "reason": ks.reason,
        "reset_by": ks.reset_by,
        "reset_at": ks.reset_at.isoformat() if ks.reset_at else None,
        "auto_triggered": ks.auto_triggered,
        "created_at": ks.created_at.isoformat(),
        "updated_at": ks.updated_at.isoformat(),
    }


@router.post("/kill-switch")
def trigger_kill_switch_endpoint(
    body: dict[str, Any],
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Trigger the global kill switch."""
    reason = body.get("reason", "Manual trigger via API")
    ks = engine_trigger_kill_switch(db=db, reason=reason, triggered_by=user.id, auto=False)
    db.commit()
    return {
        "name": ks.name,
        "state": ks.state,
        "triggered_by": ks.triggered_by,
        "triggered_at": ks.triggered_at.isoformat() if ks.triggered_at else None,
        "reason": ks.reason,
        "reset_by": ks.reset_by,
        "reset_at": ks.reset_at.isoformat() if ks.reset_at else None,
        "auto_triggered": ks.auto_triggered,
        "created_at": ks.created_at.isoformat(),
        "updated_at": ks.updated_at.isoformat(),
    }


@router.post("/kill-switch/reset")
def reset_kill_switch_endpoint(
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Reset the global kill switch."""
    ks = engine_reset_kill_switch(db=db, reset_by=user.id)
    db.commit()
    return {
        "name": ks.name,
        "state": ks.state,
        "triggered_by": ks.triggered_by,
        "triggered_at": ks.triggered_at.isoformat() if ks.triggered_at else None,
        "reason": ks.reason,
        "reset_by": ks.reset_by,
        "reset_at": ks.reset_at.isoformat() if ks.reset_at else None,
        "auto_triggered": ks.auto_triggered,
        "created_at": ks.created_at.isoformat(),
        "updated_at": ks.updated_at.isoformat(),
    }


@router.get("/risk-events")
def list_risk_events(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List paper risk events."""
    query = select(PaperRiskEvent)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    events = db.scalars(
        query.order_by(PaperRiskEvent.created_at.desc()).limit(limit).offset(offset)
    ).all()

    items = []
    for ev in events:
        items.append({
            "id": str(ev.id),
            "account_id": str(ev.account_id),
            "event_type": ev.event_type,
            "order_id": str(ev.order_id) if ev.order_id else None,
            "instrument_id": str(ev.instrument_id) if ev.instrument_id else None,
            "details": json.loads(ev.details) if isinstance(ev.details, str) else ev.details,
            "blocked": ev.blocked,
            "created_at": ev.created_at.isoformat(),
        })

    return {"total": total, "items": items}
