"""Immutable, safe projections of offline simulations; never broker orders."""

from dataclasses import asdict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtesting.engine import (
    ENGINE_VERSION,
    Result,
    SimulationConfig,
    fingerprint,
    metrics,
)
from app.backtesting.walk_forward import Fold
from app.historical.reader import VerifiedSession
from app.models import BacktestReport, WalkForwardReport
from app.strategies.contracts import StrategyConfig


def _json(value):
    """Convert only known simulation dataclasses to JSON-safe values."""
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def _metrics(result: Result) -> dict:
    return _json(asdict(result.metrics))


def _common(
    sessions: tuple[VerifiedSession, ...],
    strategy: StrategyConfig,
    config: SimulationConfig,
):
    source = sessions[0].source
    return dict(
        provider=source.provider,
        instrument_id=source.instrument_id,
        timeframe=source.timeframe,
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.version,
        simulation_config=_json(asdict(config)),
        strategy_config=_json(asdict(strategy)),
        sources=[
            dict(
                session_date=s.source.session_date.isoformat(),
                partition_id=str(s.source.partition_id),
                partition_sha256=s.source.partition_sha256,
                source_sha256=s.source.source_sha256,
                provider_key=s.source.provider_key,
            )
            for s in sessions
        ],
    )


def persist_backtest(
    db: Session,
    sessions: tuple[VerifiedSession, ...],
    strategy: StrategyConfig,
    config: SimulationConfig,
    result: Result,
) -> BacktestReport:
    existing = db.scalar(
        select(BacktestReport).where(BacktestReport.fingerprint == result.fingerprint)
    )
    if existing is not None:
        return existing
    report = BacktestReport(
        **_common(sessions, strategy, config),
        fingerprint=result.fingerprint,
        input_fingerprint=result.input_fingerprint,
        metrics=_metrics(result),
        warnings=list(result.warnings),
        trade_summary=[_json(asdict(trade)) for trade in result.trades[:100]],
        event_summary=[_json(asdict(event)) for event in result.events[:100]],
    )
    db.add(report)
    db.flush()
    return report


def persist_walk_forward(
    db: Session,
    sessions: tuple[VerifiedSession, ...],
    strategy: StrategyConfig,
    config: SimulationConfig,
    folds: tuple[Fold, ...],
    train_size: int,
    test_size: int,
) -> WalkForwardReport:
    projected = [
        dict(
            training_dates=list(fold.training_dates),
            test_dates=list(fold.test_dates),
            chosen=_json(asdict(fold.chosen)),
            training_metrics=_metrics(fold.training),
            test_metrics=_metrics(fold.test),
            training_fingerprint=fold.training.fingerprint,
            test_fingerprint=fold.test.fingerprint,
        )
        for fold in folds
    ]
    inputs = fingerprint(
        [fold.test.input_fingerprint for fold in folds]
        + [fold.training.input_fingerprint for fold in folds]
    )
    identity = fingerprint(
        dict(
            engine=ENGINE_VERSION,
            input_fingerprint=inputs,
            chosen_configs=[fold["chosen"] for fold in projected],
            simulation=_json(asdict(config)),
            train_size=train_size,
            test_size=test_size,
            folds=projected,
        )
    )
    existing = db.scalar(
        select(WalkForwardReport).where(WalkForwardReport.fingerprint == identity)
    )
    if existing is not None:
        return existing
    report = WalkForwardReport(
        **_common(sessions, strategy, config),
        fingerprint=identity,
        input_fingerprint=inputs,
        metrics=_json(
            asdict(
                metrics(tuple(trade for fold in folds for trade in fold.test.trades))
            )
        ),
        warnings=list(
            dict.fromkeys(warning for fold in folds for warning in fold.test.warnings)
        ),
        train_size=train_size,
        test_size=test_size,
        folds=projected,
    )
    db.add(report)
    db.flush()
    return report
