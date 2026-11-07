"""Paper trading module — simulation engine with risk checks.

This module provides:
- PaperOrder: Auditable order lifecycle with state transitions
- PaperPosition: Mark-to-market position tracking
- PaperFill: Immutable fill records
- PaperRiskEvent: Every blocked order is logged
- KillSwitch: Persistent kill switch that survives restarts

Usage:
    from app.paper_trading import engine, models

    # Create paper account
    account = PaperAccount(name="Demo Account", initial_capital=Decimal("1000000"))

    # Submit order with risk validation
    engine = PaperTradingEngine(db)
    result = engine.submit_order(account, instrument, PaperOrderSide.BUY, Decimal("100"))

    # Check kill switch
    if is_kill_switch_armed(db):
        # Safe to proceed
        pass
"""

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
from app.paper_trading.engine import (
    PaperTradingEngine,
    RiskContext,
    RiskResult,
    validate_order_risks,
    check_kill_switch,
    trigger_kill_switch,
    reset_kill_switch,
)

__all__ = [
    "models",
    "engine",
    "KillSwitch",
    "KillSwitchState",
    "PaperAccount",
    "PaperFill",
    "PaperOrder",
    "PaperOrderSide",
    "PaperOrderState",
    "PaperOrderType",
    "PaperPosition",
    "PaperRiskEvent",
    "PaperRiskEventType",
    "PaperTradingEngine",
    "RiskContext",
    "RiskResult",
    "validate_order_risks",
    "check_kill_switch",
    "trigger_kill_switch",
    "reset_kill_switch",
]