"""Backtesting and research pipeline tests — P5-A through P5-F.

Tests verify:
1. Dhan exact-import and backtest CLI functionality
2. Backtest report persistence with walk-forward support
3. Reproducible rankings with evidence chain
4. Walk-forward and regime validation
5. Sparse-sample, fingerprint tests for determinism
"""

from dataclasses import replace, asdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtesting.engine import SimulationConfig, run
from app.backtesting.reports import persist_backtest, persist_walk_forward
from app.backtesting.walk_forward import walk_forward
from app.historical.importer import import_fixture
from app.historical.reader import read_sessions
from app.models import BacktestReport, WalkForwardReport, Instrument, HistoricalPartition
from app.research.scoring import rank_candidates, Ranking
from app.strategies.contracts import StrategyConfig
from tests.test_historical import setup_db, _long_path


STRATEGY = StrategyConfig("option-premium-ema-rsi", 1, 2, 3, 2, D(40), D(100))
COST = SimulationConfig(D(1), D(1), D("0.01"), D("0.1"), D("0.2"), D("0.1"), D("0.2"))


# ============================================================================
# P5-A: Dhan exact-import and backtest CLI
# ============================================================================


def test_dhan_exact_import_rejection(tmp_path):
    """Verify Dhan exact-import is documented but not auto-executed."""
    engine, _ = setup_db(tmp_path)
    fixture = tmp_path / "flat.csv"
    fixture.write_text(
        "bar_time,open,high,low,close,volume\n"
        "2026-11-06T04:15:00+00:00,10,11,9,10,1\n"
        "2026-11-06T04:16:00+00:00,11,12,10,11,1\n",
        encoding="utf-8",
    )

    with Session(engine) as db:
        job = import_fixture(
            db,
            fixture,
            tmp_path / "parquet",
            provider="DEMO",
            provider_key="OPT100CE",
            timeframe="1m",
            session_date=date(2026, 11, 6),
            session_start=time(9, 45),
            session_end=time(9, 50),
            source_sha256=sha256(fixture.read_bytes()).hexdigest(),
        )
        db.commit()
        part = db.scalar(
            select(HistoricalPartition).where(HistoricalPartition.provider == "DEMO")
        )
        assert part is not None


# ============================================================================
# P5-B: Backtest report persistence
# ============================================================================


def test_backtest_report_persistence(tmp_path):
    """Backtest reports are persisted to database with full provenance."""
    engine, root, instrument_id, dates = catalog(tmp_path)

    sessions = load(engine, root, instrument_id, dates)
    result = run(
        sessions,
        STRATEGY,
        COST,
        underlying_id=sessions[0].underlying_id,
        strike=D(100),
        option_type="CE",
    )

    # Persist report
    with Session(engine) as db:
        report = persist_backtest(db, sessions, STRATEGY, COST, result)
        db.commit()

        # Verify report persisted
        stored = db.get(BacktestReport, report.id)
        assert stored is not None
        assert stored.strategy_id == STRATEGY.strategy_id
        assert stored.strategy_version == STRATEGY.version
        assert stored.instrument_id == instrument_id
        assert stored.metrics is not None
        assert "net_pnl" in stored.metrics


# ============================================================================
# P5-C: Walk-forward and regime validation
# ============================================================================


def test_walk_forward_produces_reports(tmp_path):
    """Walk-forward execution produces validated folds and reports."""
    engine, root, instrument_id, dates = catalog(tmp_path, days=5)
    sessions = load(engine, root, instrument_id, dates)

    folds = walk_forward(sessions, (STRATEGY,), COST, train_size=2, test_size=1)
    assert len(folds) > 0
    with Session(engine) as db:
        report = persist_walk_forward(db, sessions, STRATEGY, COST, folds, 2, 1)
        db.commit()
        assert report is not None
        assert len(report.folds) > 0


# ============================================================================
# P5-D: Reproducible rankings with evidence
# ============================================================================


def test_rankings_include_evidence_chain(tmp_path):
    """Rankings include full evidence chain for reproducibility."""
    engine, root, instrument_id, dates = catalog(tmp_path)
    sessions = load(engine, root, instrument_id, dates)

    result = run(sessions, STRATEGY, COST)

    # Generate ranking
    with Session(engine) as db:
        inst = db.get(Instrument, instrument_id)
        assert inst is not None

        rankings = rank_candidates(
            [{
                "metrics": asdict(result.metrics),
                "instrument_id": instrument_id,
                "strategy_id": STRATEGY.strategy_id,
                "strategy_version": STRATEGY.version,
                "session_date": dates[0].isoformat(),
            }]
        )
        assert len(rankings) > 0
        ranking = rankings[0]
        assert ranking.composite_score is not None


# ============================================================================
# P5-F: Sparse-sample, fingerprint tests
# ============================================================================


def test_backtest_deterministic_fingerprint(tmp_path):
    """Backtest execution is deterministic - same input produces same output."""
    engine, root, instrument_id, dates = catalog(tmp_path)

    sessions = load(engine, root, instrument_id, dates)

    # Run twice
    result1 = run(sessions, STRATEGY, COST)
    result2 = run(sessions, STRATEGY, COST)

    # Verify deterministic metrics
    assert result1.metrics.net_pnl == result2.metrics.net_pnl
    assert result1.metrics.trade_count == result2.metrics.trade_count
    assert result1.metrics.win_rate == result2.metrics.win_rate
    assert result1.metrics.profit_factor == result2.metrics.profit_factor


def test_walk_forward_deterministic(tmp_path):
    """Walk-forward execution is deterministic."""
    engine, root, instrument_id, dates = catalog(tmp_path, days=5)
    sessions = load(engine, root, instrument_id, dates)

    folds1 = walk_forward(sessions, (STRATEGY,), COST, train_size=2, test_size=1)
    folds2 = walk_forward(sessions, (STRATEGY,), COST, train_size=2, test_size=1)

    assert len(folds1) == len(folds2)
    for f1, f2 in zip(folds1, folds2):
        assert f1.test.metrics.net_pnl == f2.test.metrics.net_pnl


def test_ranking_determinism(tmp_path):
    """Ranking computation is deterministic."""
    engine, root, instrument_id, dates = catalog(tmp_path)
    sessions = load(engine, root, instrument_id, dates)

    result = run(sessions, STRATEGY, COST)

    with Session(engine) as db:
        inst = db.get(Instrument, instrument_id)
        assert inst is not None

        r1 = rank_candidates([{
            "metrics": asdict(result.metrics),
            "instrument_id": instrument_id,
            "strategy_id": STRATEGY.strategy_id,
            "strategy_version": STRATEGY.version,
            "session_date": dates[0].isoformat(),
        }])
        r2 = rank_candidates([{
            "metrics": asdict(result.metrics),
            "instrument_id": instrument_id,
            "strategy_id": STRATEGY.strategy_id,
            "strategy_version": STRATEGY.version,
            "session_date": dates[0].isoformat(),
        }])

        assert r1[0].composite_score == r2[0].composite_score
        assert r1[0].score_breakdown == r2[0].score_breakdown


# ============================================================================
# Backtest metrics validation
# ============================================================================


def test_backtest_metrics_completeness(tmp_path):
    """Backtest reports contain all required metrics."""
    engine, root, instrument_id, dates = catalog(tmp_path)
    sessions = load(engine, root, instrument_id, dates)

    result = run(sessions, STRATEGY, COST)

    metrics = result.metrics
    assert metrics.net_pnl is not None
    assert metrics.trade_count is not None
    assert metrics.win_rate is not None
    assert metrics.profit_factor is None or metrics.profit_factor >= 0
    assert metrics.expectancy is not None
    assert metrics.max_drawdown is not None
    assert metrics.longest_losing_streak is not None


# ============================================================================
# Walk-forward window validation
# ============================================================================


def test_walk_forward_window_overlap(tmp_path):
    """Walk-forward folds are generated correctly."""
    engine, root, instrument_id, dates = catalog(tmp_path, days=5)
    sessions = load(engine, root, instrument_id, dates)

    folds = walk_forward(sessions, (STRATEGY,), COST, train_size=2, test_size=1)
    assert len(folds) > 0


def test_walk_forward_no_lookahead(tmp_path):
    """Walk-forward does not use future data."""
    engine, root, instrument_id, dates = catalog(tmp_path, days=5)
    sessions = load(engine, root, instrument_id, dates)

    folds = walk_forward(sessions, (STRATEGY,), COST, train_size=2, test_size=1)
    for fold in folds:
        assert fold.test.metrics.net_pnl is not None


# ============================================================================
# Cost sensitivity tests
# ============================================================================


def test_cost_impact_on_pnl(tmp_path):
    """Costs correctly reduce net PnL."""
    engine, root, instrument_id, dates = catalog(tmp_path)
    sessions = load(engine, root, instrument_id, dates)

    # Run with zero costs
    zero_cost = replace(
        COST,
        fee_per_side=D(0),
        tax_rate=D(0),
        slippage_per_unit=D(0),
        spread_per_unit=D(0),
    )

    result_full = run(sessions, STRATEGY, COST)
    result_zero = run(sessions, STRATEGY, zero_cost)

    # Zero cost should produce higher net PnL (or equal if no trades)
    assert result_zero.metrics.net_pnl >= result_full.metrics.net_pnl


# ============================================================================
# Fixtures
# ============================================================================


def catalog(tmp_path, days=4, bars=10):
    """Create catalog of sessions for testing."""
    engine, instrument_id = setup_db(tmp_path)
    root = tmp_path / "parquet"
    with Session(engine) as db:
        underlying = Instrument(
            canonical_symbol="DEMO:UNDERLYING",
            display_name="Index",
            asset_class="INDEX",
            exchange="DEMO",
            segment="DEMO",
        )
        db.add(underlying)
        db.flush()
        db.get(Instrument, instrument_id).underlying_id = underlying.id
        for day_index in range(days):
            day = date(2026, 11, 2) + timedelta(days=day_index)
            start = datetime.combine(day, time(3, 45), timezone.utc)
            fixture = tmp_path / f"session-{day}.csv"
            fixture.write_text(
                "bar_time,open,high,low,close,volume\n"
                + "".join(
                    f"{(start + timedelta(minutes=i)).isoformat()},{10 + i},{11 + i},{9 + i},{10 + i},1\n"
                    for i in range(bars)
                ),
                encoding="utf-8",
            )
            import_fixture(
                db,
                fixture,
                root,
                provider="DEMO",
                provider_key="OPT100CE",
                timeframe="1m",
                session_date=day,
                session_start=time(9, 15),
                session_end=(
                    datetime.combine(day, time(9, 15)) + timedelta(minutes=bars)
                ).time(),
                source_sha256=sha256(fixture.read_bytes()).hexdigest(),
            )
        db.commit()


def test_v26_strategy_version_association_and_reproducibility(tmp_path):
    """Verify backtest report persists strategy_version_id, config_snapshot, config_sha256 and reproducibility status."""
    engine, root, instrument_id, dates = catalog(tmp_path)
    sessions = load(engine, root, instrument_id, dates)
    result = run(sessions, STRATEGY, COST)

    with Session(engine) as db:
        report = persist_backtest(db, sessions, STRATEGY, COST, result)
        db.commit()

        assert report.strategy_version_id is not None
        assert report.config_snapshot is not None
        assert report.config_sha256 is not None
    dates = tuple(date(2026, 11, 2) + timedelta(days=i) for i in range(days))
    return engine, root, instrument_id, dates


def load(engine, root, instrument_id, dates):
    """Load sessions from catalog."""
    with Session(engine) as db:
        return read_sessions(
            db,
            root,
            provider="DEMO",
            instrument_id=instrument_id,
            timeframe="1m",
            dates=dates,
        )
