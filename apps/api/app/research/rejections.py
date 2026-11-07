"""Versioned rejection rule engine.

Each rule is a simple threshold check.  A candidate is rejected if
ANY rule fires.  Rejection is independent of scoring.
"""

from __future__ import annotations

from decimal import Decimal


VERSION = 1

REJECTION_RULES = {
    "min_trades": 5,
    "max_drawdown_pct_of_pnl": Decimal("50"),
    "min_win_rate": Decimal("30"),
    "max_losing_streak": 5,
    "min_sessions": 2,
}


def _safe_decimal(value, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    return Decimal(str(value))


def check_rejections(metrics: dict, session_count: int) -> tuple[bool, tuple[str, ...]]:
    """Apply rejection rules. Returns (is_rejected, reasons)."""
    reasons: list[str] = []

    trade_count = int(metrics.get("trade_count") or 0)
    if trade_count < REJECTION_RULES["min_trades"]:
        reasons.append(
            f"INSUFFICIENT_TRADES: {trade_count} < {REJECTION_RULES['min_trades']}"
        )

    max_dd = _safe_decimal(metrics.get("max_drawdown"))
    net_pnl = _safe_decimal(metrics.get("net_pnl"))
    if net_pnl != 0 and max_dd > abs(net_pnl) * REJECTION_RULES["max_drawdown_pct_of_pnl"] / Decimal("100"):
        reasons.append("EXCESSIVE_DRAWDOWN")

    win_rate = metrics.get("win_rate")
    if win_rate is not None:
        wr = _safe_decimal(win_rate) * Decimal("100")
        if wr < REJECTION_RULES["min_win_rate"]:
            reasons.append(f"LOW_WIN_RATE: {float(wr):.1f}% < {float(REJECTION_RULES['min_win_rate']):.0f}%")

    losing_streak = int(metrics.get("longest_losing_streak") or 0)
    if losing_streak > REJECTION_RULES["max_losing_streak"]:
        reasons.append(
            f"LONG_LOSE_STREAK: {losing_streak} > {REJECTION_RULES['max_losing_streak']}"
        )

    if session_count < REJECTION_RULES["min_sessions"]:
        reasons.append(
            f"INSUFFICIENT_SESSIONS: {session_count} < {REJECTION_RULES['min_sessions']}"
        )

    return (len(reasons) > 0, tuple(reasons))
