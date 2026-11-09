"""Paper execution service — bridges project signals to paper trading engine.

All paper signals, validation, risk checks, orders, fills, and position updates
flow through this atomic service. Zero broker coupling.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Instrument, StrategyVersion
from app.paper_trading.engine import PaperTradingEngine, PaperExecutionResult
from app.paper_trading.models import (
    PaperAccount,
    PaperOrder,
    PaperOrderSide,
    PaperOrderType,
    PaperSignal,
    PaperSignalStatus,
)
from app.projects.models import Project


class PaperExecutionService:
    """Service handling durable paper signal intake, risk validation, and execution."""

    @staticmethod
    def submit_signal(
        db: Session,
        project: Project,
        strategy_version: StrategyVersion,
        instrument: Instrument,
        account: PaperAccount,
        direction: str,  # 'LONG' or 'SHORT'
        signal_type: str,  # 'ENTRY' or 'EXIT'
        requested_quantity: Decimal,
        correlation_id: str,
        reference_price: Decimal | None = None,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
    ) -> tuple[PaperSignal, PaperExecutionResult | None]:
        """Submit a paper signal idempotently and execute through the paper engine if validated."""
        # 1. Check idempotency: does correlation_id already exist?
        existing_signal = db.execute(
            select(PaperSignal).where(PaperSignal.correlation_id == correlation_id)
        ).scalar_one_or_none()

        if existing_signal:
            # Return existing signal and execution result if order exists
            return existing_signal, None

        # 2. Create PaperSignal in RECEIVED state
        signal = PaperSignal(
            project_id=project.id,
            strategy_version_id=strategy_version.id,
            instrument_id=instrument.id,
            direction=direction.upper(),
            signal_type=signal_type.upper(),
            requested_quantity=requested_quantity,
            reference_price=reference_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status=PaperSignalStatus.RECEIVED,
            correlation_id=correlation_id,
        )
        db.add(signal)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existing = db.execute(
                select(PaperSignal).where(PaperSignal.correlation_id == correlation_id)
            ).scalar_one()
            return existing, None

        # 3. Translate direction and signal_type to PaperOrderSide
        # LONG ENTRY -> BUY, LONG EXIT -> SELL
        # SHORT ENTRY -> SELL, SHORT EXIT -> BUY (or position close)
        if direction.upper() == "LONG":
            side = PaperOrderSide.BUY if signal_type.upper() == "ENTRY" else PaperOrderSide.SELL
        else:
            side = PaperOrderSide.SELL if signal_type.upper() == "ENTRY" else PaperOrderSide.BUY

        # 4. Invoke PaperTradingEngine
        engine = PaperTradingEngine(db)

        # Mark signal validated
        signal.status = PaperSignalStatus.VALIDATED

        exec_result = engine.submit_order(
            account=account,
            instrument=instrument,
            side=side,
            quantity=requested_quantity,
            order_type=PaperOrderType.MARKET,
            price=reference_price,
            strategy_id=project.slug,
        )

        # 5. Link traceability on PaperOrder and update Signal status
        if exec_result.order:
            exec_result.order.project_id = project.id
            exec_result.order.strategy_version_id = strategy_version.id
            exec_result.order.signal_id = signal.id

            if exec_result.success and exec_result.order.state in ("filled", "partial", "submitted"):
                signal.status = PaperSignalStatus.SUBMITTED if exec_result.order.state == "submitted" else PaperSignalStatus.COMPLETED
            else:
                signal.status = PaperSignalStatus.REJECTED
                signal.reason = exec_result.rejected_reason or "Execution rejected by risk or kill switch"
        else:
            signal.status = PaperSignalStatus.REJECTED
            signal.reason = exec_result.rejected_reason or "Order creation failed"

        db.commit()
        db.refresh(signal)
        return signal, exec_result
