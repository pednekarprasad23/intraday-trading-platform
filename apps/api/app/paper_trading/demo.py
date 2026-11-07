"""Phase 5 demo order test endpoints — for controlled demo order submission.

WARNING: These endpoints are for operator verification only.
They are NOT broker execution endpoints.

This module provides:
1. Demo order submission (simulated execution)
2. MT5 terminal verification
3. Order lifecycle testing
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.auth import require_user
from app.database import get_db
from app.models import Instrument
from app.paper_trading.engine import (
    PaperTradingEngine,
    PaperOrderSide,
    PaperOrderType,
    is_kill_switch_armed,
    trigger_kill_switch,
)
from app.paper_trading.models import (
    PaperAccount,
    PaperOrderState,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


router = APIRouter(prefix="/api/v1/demo", dependencies=[Depends(require_user)])


class DemoOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_canonical: str  # e.g., "NIFTY", "RELIANCE", "XAUUSD"
    side: Literal["buy", "sell"]
    quantity: Decimal
    price: Decimal | None = None
    order_type: Literal["market", "limit", "stop", "stop_limit"] = "market"
    provider: Literal["DHAN", "MT5", "DEMO"] = "DEMO"
    test_scenario: Literal["normal", "insufficient_capital", "kill_switch"] = "normal"


class DemoOrderResponse(BaseModel):
    id: str
    instrument_canonical: str
    side: str
    quantity: Decimal
    price: Decimal | None
    state: str
    success: bool
    rejection_reason: str | None = None
    simulated_at: str


class DemoAccountResponse(BaseModel):
    name: str
    currency: str
    initial_capital: str
    available_capital: str
    max_position_value: str
    is_active: bool


@router.get("/account", response_model=DemoAccountResponse)
def get_demo_account(db: Session = Depends(get_db)):
    """Get the demo paper account."""
    account = db.scalar(
        select(PaperAccount).where(PaperAccount.name == "Demo Account")
    )
    if account is None:
        # Create default demo account
        account = PaperAccount(
            name="Demo Account",
            currency="INR",
            initial_capital=Decimal("10000000"),  # 1 Crore
            available_capital=Decimal("10000000"),
            max_position_value=Decimal("5000000"),
            max_daily_loss=Decimal("500000"),
            max_total_exposure=Decimal("10000000"),
        )
        db.add(account)
        db.flush()

    return DemoAccountResponse(
        name=account.name,
        currency=account.currency,
        initial_capital=str(account.initial_capital),
        available_capital=str(account.available_capital),
        max_position_value=str(account.max_position_value),
        is_active=account.is_active,
    )


@router.post("/orders", response_model=DemoOrderResponse)
def submit_demo_order(
    request: DemoOrderRequest,
    db: Session = Depends(get_db),
):
    """
    Submit a demo order for testing paper trading.

    This endpoint:
    1. Validates the instrument exists
    2. Checks all risk limits
    3. Simulates execution (no real broker interaction)
    4. Returns result for verification

    USE ONLY FOR OPERATOR TESTING.
    """

    # Get or create demo account
    account = db.scalar(
        select(PaperAccount).where(PaperAccount.name == "Demo Account")
    )
    if account is None:
        account = PaperAccount(
            name="Demo Account",
            currency="INR",
            initial_capital=Decimal("10000000"),
            available_capital=Decimal("10000000"),
            max_position_value=Decimal("5000000"),
            max_daily_loss=Decimal("500000"),
            max_total_exposure=Decimal("10000000"),
        )
        db.add(account)
        db.flush()

    # Find instrument by canonical symbol
    if request.provider == "MT5":
        # Use MT5Symbols for crypto/commodity
        from app.instruments.mappings import MT5_SYMBOLS
        symbol_info = MT5_SYMBOLS.get(request.instrument_canonical)
        if symbol_info is None:
            raise HTTPException(status_code=404, detail="Instrument not found")
        # For MT5 instruments, we create a placeholder
        inst = Instrument(
            canonical_symbol=request.instrument_canonical,
            display_name=f"{request.instrument_canonical} (Simulated)",
            asset_class="COMMODITY" if "XAUUSD" in request.instrument_canonical else "CRYPTO",
            exchange="MT5",
            segment="COMMODITY" if "XAUUSD" in request.instrument_canonical else "CRYPTO",
        )
        db.add(inst)
        db.flush()
    else:
        # Find existing instrument
        inst = db.scalar(
            select(Instrument).where(Instrument.canonical_symbol == request.instrument_canonical)
        )
        if inst is None:
            raise HTTPException(status_code=404, detail=f"Instrument {request.instrument_canonical} not found")

    # Determine price: use request.price, or default for market orders
    price = request.price
    if price is None and request.order_type == "market":
        price = Decimal("1000")

    # Handle test scenarios
    if request.test_scenario == "insufficient_capital":
        # Force capital check to fail by setting a very high price
        price = Decimal("1000000000")

    if request.test_scenario == "kill_switch":
        trigger_kill_switch(db, "Demo test trigger")
        db.commit()
        # Re-fetch account after commit
        account = db.scalar(
            select(PaperAccount).where(PaperAccount.name == "Demo Account")
        )

    # Convert side and order_type
    side = PaperOrderSide.BUY if request.side == "buy" else PaperOrderSide.SELL
    order_type_map = {
        "market": PaperOrderType.MARKET,
        "limit": PaperOrderType.LIMIT,
        "stop": PaperOrderType.STOP,
        "stop_limit": PaperOrderType.STOP_LIMIT,
    }
    order_type = order_type_map[request.order_type]

    # Execute via engine
    try:
        engine = PaperTradingEngine(db)
        result = engine.submit_order(
            account=account,
            instrument=inst,
            side=side,
            quantity=request.quantity,
            order_type=order_type,
            price=price,
            stop_price=request.stop_price,
        )

        return DemoOrderResponse(
            id=str(result.order.id),
            instrument_canonical=request.instrument_canonical,
            side=request.side,
            quantity=request.quantity,
            price=price if request.test_scenario != "insufficient_capital" else request.price,
            state=result.order.state,
            success=result.success,
            rejection_reason=result.rejected_reason,
            simulated_at=datetime.now(timezone.utc).isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return DemoOrderResponse(
            id="",
            instrument_canonical=request.instrument_canonical,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            state=PaperOrderState.REJECTED.value,
            success=False,
            rejection_reason=str(e),
            simulated_at=datetime.now(timezone.utc).isoformat(),
        )
