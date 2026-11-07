"""Deterministic candidate scoring engine.

Takes backtest / walk-forward metrics and structure analysis results
as inputs.  Computes a composite deterministic score from multiple
weighted components.  Returns a ``Ranking`` dataclass.

No database access.  Pure-Python.  Versioned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.research.rulebook import (
    NORMALIZATION,
    REJECTION_RULES,
    SCORING_WEIGHTS,
    VERSION as RULES_VERSION,
)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ranking:
    """Immutable ranking for a single candidate."""

    candidate_id: str
    strategy_id: str
    strategy_version: int
    instrument_id: UUID
    session_date: str
    composite_score: Decimal  # 0-100
    score_breakdown: dict  # {component: score}
    sub_scores: dict  # {metric: normalized_score}
    is_rejected: bool
    rejection_reasons: tuple[str, ...]
    ranking_version: int
    computed_at: datetime
    evidence: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _normalize(value: Decimal, metric: str) -> Decimal:
    lo, hi = NORMALIZATION[metric]
    lo_d = Decimal(str(lo))
    hi_d = Decimal(str(hi))
    if hi_d == lo_d:
        return Decimal("0")
    return (_clamp(value, lo_d, hi_d) - lo_d) * Decimal("100") / (hi_d - lo_d)


def _safe_decimal(value, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    return Decimal(str(value))


# ---------------------------------------------------------------------------
# Component scorers
# ---------------------------------------------------------------------------


def _compute_performance_score(metrics: dict) -> tuple[Decimal, dict]:
    """Performance component: net_pnl, win_rate, profit_factor, expectancy."""
    net_pnl = _safe_decimal(metrics.get("net_pnl"))
    win_rate = _safe_decimal(metrics.get("win_rate"))
    profit_factor = _safe_decimal(metrics.get("profit_factor"))
    expectancy = _safe_decimal(metrics.get("expectancy"))

    net_pnl_norm = _normalize(net_pnl, "net_pnl")
    win_rate_norm = _normalize(win_rate, "win_rate")
    pf_norm = _normalize(profit_factor, "profit_factor")
    exp_norm = _normalize(expectancy, "expectancy")

    sub = {
        "net_pnl_norm": float(net_pnl_norm),
        "win_rate_norm": float(win_rate_norm),
        "profit_factor_norm": float(pf_norm),
        "expectancy_norm": float(exp_norm),
    }

    score = (net_pnl_norm + win_rate_norm + pf_norm + exp_norm) / Decimal("4")
    return score, sub


def _compute_risk_score(metrics: dict) -> Decimal:
    """Risk component: inverted drawdown, losing streak, drawdown-to-net."""
    max_dd = _safe_decimal(metrics.get("max_drawdown"))
    losing_streak = int(metrics.get("longest_losing_streak") or 0)
    net_pnl = _safe_decimal(metrics.get("net_pnl"))

    # Drawdown score: 0 drawdown = 100, max drawdown = 0
    dd_norm = _normalize(max_dd, "max_drawdown")
    dd_score = Decimal("100") - dd_norm

    # Losing streak score: 0 streak = 100, max streak = 0
    streak_norm = _normalize(Decimal(str(losing_streak)), "longest_losing_streak")
    streak_score = Decimal("100") - streak_norm

    # Drawdown-to-net ratio
    if net_pnl != 0 and abs(net_pnl) > 0:
        dd_to_net = max_dd / abs(net_pnl)
        if dd_to_net > Decimal("1"):
            dd_to_net_score = Decimal("0")
        else:
            dd_to_net_score = Decimal("100") - (dd_to_net * Decimal("50"))
    else:
        dd_to_net_score = Decimal("0")

    score = (dd_score + streak_score + dd_to_net_score) / Decimal("3")
    return score


def _compute_data_quality_score(metrics: dict, session_count: int) -> Decimal:
    """Data quality: trade count sufficiency, session coverage."""
    trade_count = int(metrics.get("trade_count") or 0)

    tc_norm = _normalize(Decimal(str(trade_count)), "trade_count")
    sc_norm = _normalize(Decimal(str(session_count)), "session_count")

    score = (tc_norm + sc_norm) / Decimal("2")
    return score


def _compute_structure_alignment_score(level_count: int) -> Decimal:
    """Structure alignment: how many structure levels the candidate interacts with."""
    return _normalize(Decimal(str(level_count)), "structure_level_count")


# ---------------------------------------------------------------------------
# Rejection rules
# ---------------------------------------------------------------------------


def _apply_rejection_rules(metrics: dict, session_count: int) -> tuple[bool, tuple[str, ...]]:
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def rank_candidate(
    metrics: dict,
    structure_level_count: int = 0,
    session_count: int = 0,
    instrument_id: UUID | None = None,
    strategy_id: str = "",
    strategy_version: int = 0,
    session_date: str = "",
    evidence: dict | None = None,
) -> Ranking:
    """Compute a deterministic ranking for a single candidate."""
    perf_score, perf_sub = _compute_performance_score(metrics)
    risk_score = _compute_risk_score(metrics)
    dq_score = _compute_data_quality_score(metrics, session_count)
    struct_score = _compute_structure_alignment_score(structure_level_count)

    w = SCORING_WEIGHTS
    composite = (
        perf_score * w["performance"]
        + risk_score * w["risk"]
        + dq_score * w["data_quality"]
        + struct_score * w["structure_alignment"]
    )
    composite = composite.quantize(Decimal("0.01"))

    is_rejected, rejection_reasons = _apply_rejection_rules(metrics, session_count)

    candidate_id = (
        f"{strategy_id}_v{strategy_version}_{instrument_id}_{session_date}"
        if all([strategy_id, instrument_id, session_date])
        else "unknown"
    )

    return Ranking(
        candidate_id=candidate_id,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        instrument_id=instrument_id or UUID(int=0),
        session_date=session_date,
        composite_score=composite,
        score_breakdown={
            "performance": float(perf_score.quantize(Decimal("0.01"))),
            "risk": float(risk_score.quantize(Decimal("0.01"))),
            "data_quality": float(dq_score.quantize(Decimal("0.01"))),
            "structure_alignment": float(struct_score.quantize(Decimal("0.01"))),
        },
        sub_scores=perf_sub,
        is_rejected=is_rejected,
        rejection_reasons=rejection_reasons,
        ranking_version=RULES_VERSION,
        computed_at=datetime.now(timezone.utc),
        evidence=evidence or {},
    )


def rank_candidates(candidates: list[dict]) -> list[Ranking]:
    """Rank multiple candidates and sort by composite score descending."""
    rankings = [rank_candidate(**c) for c in candidates]
    rankings.sort(key=lambda r: (-r.composite_score, r.candidate_id))
    return rankings