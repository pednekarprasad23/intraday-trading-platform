"""Strategy performance tracking and drift detection.

Provides hooks for recording backtest/walk-forward results and
tracking strategy performance history over time.
"""

from datetime import datetime, date
from decimal import Decimal as D
from typing import Optional, Any
import enum

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.backtesting.reports import BacktestReport, WalkForwardReport


class StrategyStatus(str, enum.Enum):
    """Lifecycle status for a strategy."""
    DRAFT = "draft"
    TESTING = "testing"
    LIVE = "live"
    ARCHIVED = "archived"


# In-memory strategy registry (in production, this would be in DB)
STRATEGY_REGISTRY: dict[str, dict[str, Any]] = {}


def register_strategy(
    strategy_id: str,
    name: str,
    version: str,
    description: str = "",
) -> dict[str, Any]:
    """Register a strategy in the registry.

    Args:
        strategy_id: Unique identifier for the strategy
        name: Human-readable name
        version: Version string (e.g., "1.0.0")
        description: Optional description

    Returns:
        The registered strategy metadata
    """
    registry = STRATEGY_REGISTRY.setdefault(
        strategy_id,
        {"versions": {}, "status": StrategyStatus.DRAFT.value}
    )
    registry["name"] = name
    registry["current_version"] = version
    registry["description"] = description
    registry["versions"][version] = {
        "created_at": datetime.utcnow().isoformat(),
        "metrics": [],
    }
    registry["strategy_id"] = strategy_id
    return registry


def record_performance(
    strategy_id: str,
    report: BacktestReport | WalkForwardReport,
    session_date: Optional[date] = None,
) -> dict[str, Any]:
    """Record performance for a strategy after backtest/walk-forward.

    Args:
        strategy_id: Strategy identifier
        report: BacktestReport or WalkForwardReport instance
        session_date: Optional session date (defaults to today)

    Returns:
        Record of the performance snapshot
    """
    if session_date is None:
        session_date = date.today()

    # Extract key metrics from report
    metrics = {}
    if hasattr(report, "metrics") and report.metrics:
        metrics = dict(report.metrics)
    else:
        # Fallback for different report types
        metrics = {
            "total_return": getattr(report, "total_return", D(0)),
            "sharpe_ratio": getattr(report, "sharpe_ratio", 0),
            "max_drawdown": getattr(report, "max_drawdown", D(0)),
            "win_rate": getattr(report, "win_rate", 0),
            "profit_factor": getattr(report, "profit_factor", 0),
        }

    snapshot = {
        "strategy_id": strategy_id,
        "version": getattr(report, "strategy_version", "1.0.0"),
        "session_date": session_date.isoformat(),
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": metrics,
        "fingerprint": getattr(report, "fingerprint", None),
    }

    # Store in registry
    if strategy_id not in STRATEGY_REGISTRY:
        register_strategy(strategy_id, strategy_id, snapshot["version"])

    registry = STRATEGY_REGISTRY[strategy_id]
    registry["versions"][snapshot["version"]]["metrics"].append(snapshot)

    result = dict(snapshot)
    result["strategy_id"] = strategy_id
    return result


def get_strategy_history(
    strategy_id: str,
    db: Optional[Session] = None,
) -> list[dict[str, Any]]:
    """Get time-series of scores/metrics for a strategy.

    Args:
        strategy_id: Strategy identifier
        db: Optional database session

    Returns:
        List of performance snapshots ordered by date (newest first)
    """
    if strategy_id not in STRATEGY_REGISTRY:
        return []

    version_metrics = STRATEGY_REGISTRY[strategy_id]["versions"]

    all_snapshots = []
    for version, data in version_metrics.items():
        for snapshot in data.get("metrics", []):
            all_snapshots.append(snapshot)

    # Sort by session_date descending
    all_snapshots.sort(key=lambda x: x.get("session_date", ""), reverse=True)

    return all_snapshots


def get_lifecycle(
    strategy_id: str,
) -> dict[str, Any]:
    """Get the lifecycle status and metadata for a strategy.

    Args:
        strategy_id: Strategy identifier

    Returns:
        Strategy lifecycle information including status, versions, and metrics
    """
    if strategy_id not in STRATEGY_REGISTRY:
        return {
            "strategy_id": strategy_id,
            "status": StrategyStatus.DRAFT.value,
            "versions": {},
            "current_version": None,
            "name": strategy_id,
        }

    return STRATEGY_REGISTRY[strategy_id].copy()


def detect_drift(
    strategy_id: str,
    threshold: D = D("0.1"),
    lookback_days: int = 30,
) -> dict[str, Any]:
    """Detect performance drift between recent and historical performance.

    Compares the most recent performance against historical performance
    to detect significant changes that may indicate strategy drift.

    Args:
        strategy_id: Strategy identifier
        threshold: Maximum acceptable drift ratio (default 0.1 = 10%)
        lookback_days: Number of days to compare against

    Returns:
        Drift analysis report
    """
    history = get_strategy_history(strategy_id)

    if len(history) < 2:
        return {
            "strategy_id": strategy_id,
            "drift_detected": False,
            "reason": "insufficient_history",
            "historical_metrics": None,
            "recent_metrics": None,
        }

    # Get most recent and historical snapshots
    recent = history[0]

    # Find historical snapshot within lookback
    recent_date = datetime.fromisoformat(recent["session_date"])
    historical = None

    for snapshot in history[1:]:
        snapshot_date = datetime.fromisoformat(snapshot["session_date"])
        days_diff = (recent_date - snapshot_date).days
        if days_diff <= lookback_days:
            historical = snapshot
            break

    if historical is None:
        return {
            "strategy_id": strategy_id,
            "drift_detected": False,
            "reason": "no_historical_data_in_lookback",
            "historical_metrics": None,
            "recent_metrics": recent.get("metrics"),
        }

    # Compare key metrics
    recent_metrics = recent.get("metrics", {})
    historical_metrics = historical.get("metrics", {})

    drifts = {}
    drift_detected = False

    for metric in ["total_return", "sharpe_ratio", "max_drawdown", "win_rate"]:
        if metric in recent_metrics and metric in historical_metrics:
            recent_val = D(str(recent_metrics[metric]))
            historical_val = D(str(historical_metrics[metric]))

            if historical_val != 0:
                drift_ratio = abs((recent_val - historical_val) / historical_val)
                drifts[metric] = {
                    "recent": float(recent_val),
                    "historical": float(historical_val),
                    "drift_ratio": float(drift_ratio),
                    "status": "WARNING" if drift_ratio > float(threshold) else "OK",
                }

                if drift_ratio > threshold:
                    drift_detected = True

    return {
        "strategy_id": strategy_id,
        "drift_detected": drift_detected,
        "threshold": float(threshold),
        "historical_metrics": historical_metrics,
        "recent_metrics": recent_metrics,
        "drifts": drifts,
        "comparison_date": historical.get("session_date"),
        "analysis_date": recent.get("session_date"),
    }


def get_strategy_versions(
    strategy_id: str,
) -> dict[str, Any]:
    """Get strategy version history for monitoring dashboard.

    Args:
        strategy_id: Strategy identifier

    Returns:
        Dictionary of versions with their creation dates and snapshot counts
    """
    if strategy_id not in STRATEGY_REGISTRY:
        return {
            "strategy_id": strategy_id,
            "versions": {},
            "current_version": None,
            "total_snapshots": 0,
        }

    registry = STRATEGY_REGISTRY[strategy_id]
    versions = {}
    total_snapshots = 0

    for version, data in registry.get("versions", {}).items():
        snapshots = data.get("metrics", [])
        total_snapshots += len(snapshots)
        versions[version] = {
            "created_at": data.get("created_at"),
            "snapshot_count": len(snapshots),
            "latest_metrics": snapshots[-1] if snapshots else None,
        }

    return {
        "strategy_id": strategy_id,
        "name": registry.get("name"),
        "current_version": registry.get("current_version"),
        "status": registry.get("status"),
        "versions": versions,
        "total_snapshots": total_snapshots,
    }