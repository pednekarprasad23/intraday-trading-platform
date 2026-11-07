"""Versioned scoring weights, normalization bounds, and rejection thresholds.

Each rule set carries a VERSION.  When rules evolve, increment the
version so past rankings remain traceable.
"""

from decimal import Decimal

# ---------------------------------------------------------------------------
# Scoring weights -- must sum to 1.0
# ---------------------------------------------------------------------------

VERSION = 1

SCORING_WEIGHTS = {
    "performance": Decimal("0.35"),
    "risk": Decimal("0.30"),
    "data_quality": Decimal("0.20"),
    "structure_alignment": Decimal("0.15"),
}

# ---------------------------------------------------------------------------
# Normalization bounds (min, max) for linear interpolation to 0-100
# ---------------------------------------------------------------------------

NORMALIZATION = {
    "net_pnl": (Decimal("-1000"), Decimal("1000")),
    "win_rate": (Decimal("0"), Decimal("1")),
    "profit_factor": (Decimal("0"), Decimal("5")),
    "expectancy": (Decimal("-10"), Decimal("10")),
    "max_drawdown": (Decimal("0"), Decimal("500")),
    "longest_losing_streak": (0, 20),
    "trade_count": (0, 200),
    "session_count": (0, 50),
    "structure_level_count": (0, 10),
}

# ---------------------------------------------------------------------------
# Rejection thresholds
# ---------------------------------------------------------------------------

REJECTION_RULES = {
    "min_trades": 5,
    "max_drawdown_pct_of_pnl": Decimal("50"),
    "min_win_rate": Decimal("30"),
    "max_losing_streak": 5,
    "min_sessions": 2,
}
