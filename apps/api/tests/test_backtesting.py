from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtesting.engine import SimulationConfig, run
from app.backtesting.walk_forward import walk_forward
from app.historical.importer import import_fixture
from app.historical.reader import read_sessions
from app.models import HistoricalPartition, Instrument
from app.strategies.contracts import StrategyConfig
from tests.test_historical import setup_db, _long_path

STRATEGY = StrategyConfig("option-premium-ema-rsi", 1, 2, 3, 2, D(40), D(100))
COST = SimulationConfig(D(1), D(1), D("0.01"), D("0.1"), D("0.2"), D("0.1"), D("0.2"))


def catalog(tmp_path, days=4, bars=10):
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
    dates = tuple(date(2026, 11, 2) + timedelta(days=i) for i in range(days))
    return engine, root, instrument_id, dates


def load(engine, root, instrument_id, dates):
    with Session(engine) as db:
        return read_sessions(
            db,
            root,
            provider="DEMO",
            instrument_id=instrument_id,
            timeframe="1m",
            dates=dates,
        )


def test_verified_reader_rejects_gaps_tampering_and_absent_sessions(tmp_path):
    engine, root, identity, dates = catalog(tmp_path)
    sessions = load(engine, root, identity, dates)
    assert len(sessions) == 4 and len(sessions[0].bars) == 10
    with pytest.raises(ValueError, match="Missing"):
        load(engine, root, identity, dates + (date(2026, 11, 7),))
    with Session(engine) as db:
        part = db.scalar(
            select(HistoricalPartition).where(
                HistoricalPartition.session_date == dates[0]
            )
        )
        path = root / part.relative_path
        path_long = _long_path(path)
        with open(path_long, "rb") as f:
            original = f.read()
        with open(path_long, "wb") as f:
            f.write(b"corrupted")
        with pytest.raises(ValueError, match="checksum"):
            read_sessions(
                db,
                root,
                provider="DEMO",
                instrument_id=identity,
                timeframe="1m",
                dates=dates[:1],
            )
        with open(path_long, "wb") as f:
            f.write(original)
        part.relative_path = "../escape.parquet"
        db.flush()
        with pytest.raises(ValueError, match="path"):
            read_sessions(
                db,
                root,
                provider="DEMO",
                instrument_id=identity,
                timeframe="1m",
                dates=dates[:1],
            )


def test_replay_no_lookahead_costs_and_expiry(tmp_path):
    engine, root, identity, dates = catalog(tmp_path)
    sessions = load(engine, root, identity, dates)
    result = run(
        sessions,
        STRATEGY,
        COST,
        underlying_id=sessions[0].underlying_id,
        strike=D(100),
        option_type="CE",
    )
    assert result == run(sessions, STRATEGY, COST)
    assert result.trades and result.metrics.trade_count == len(result.trades)
    assert all(
        trade.entry_time >= signal.time
        for signal, trade in zip(
            (e for e in result.events if e.kind == "SIGNAL"), result.trades
        )
    )
    assert all(t.exit_time.date() == t.entry_time.date() for t in result.trades)
    zero = replace(
        COST,
        fee_per_side=D(0),
        tax_rate=D(0),
        slippage_per_unit=D(0),
        spread_per_unit=D(0),
    )
    assert result.metrics.net_pnl < run(sessions, STRATEGY, zero).metrics.net_pnl
    with pytest.raises(ValueError, match="expiry"):
        run(
            (
                replace(
                    sessions[0],
                    source=replace(sessions[0].source, expiry_date=date(2026, 11, 1)),
                ),
            ),
            STRATEGY,
            COST,
        )
    with pytest.raises(ValueError, match="Mixing"):
        run(
            (
                sessions[0],
                replace(
                    sessions[1], source=replace(sessions[1].source, provider="OTHER")
                ),
            ),
            STRATEGY,
            COST,
        )


def test_ambiguous_stop_target_chooses_stop(tmp_path):
    engine, root, identity, dates = catalog(tmp_path, days=1)
    session = load(engine, root, identity, dates)[0]
    # Signal on bar 2, entry at bar 3. Both thresholds touch in bar 4.
    bars = list(session.bars)
    bars[4] = replace(bars[4], high=D(100), low=D(1))
    simulated = run((replace(session, bars=tuple(bars)),), STRATEGY, COST)
    assert simulated.trades[0].exit_reason == "STOP_AMBIGUOUS"
    assert simulated.trades[0].exit < simulated.trades[0].entry


def test_missing_exit_bar_and_walk_forward_isolation(tmp_path):
    engine, root, identity, dates = catalog(tmp_path)
    sessions = load(engine, root, identity, dates)
    short = replace(
        sessions[0],
        bars=sessions[0].bars[:4],
        session_end=sessions[0].bars[3].bar_time + timedelta(minutes=1),
    )
    result = run((short,), STRATEGY, COST)
    assert result.metrics.trade_count == 0 and result.metrics.expectancy is None
    assert any(e.kind == "NO_FILL" for e in result.events)
    folds = walk_forward(
        sessions,
        (STRATEGY, replace(STRATEGY, rsi_floor=D(50))),
        COST,
        train_size=2,
        test_size=1,
    )
    assert len(folds) == 2
    assert folds[0].training_dates == tuple(d.isoformat() for d in dates[:2])
    assert folds[0].test_dates == (dates[2].isoformat(),)
    altered = replace(
        sessions[2],
        bars=tuple(
            replace(b, close=b.open, high=max(b.high, b.open), low=min(b.low, b.open))
            for b in sessions[2].bars
        ),
    )
    changed = walk_forward(
        sessions[:2] + (altered,) + sessions[3:],
        (STRATEGY, replace(STRATEGY, rsi_floor=D(50))),
        COST,
        train_size=2,
        test_size=1,
    )
    assert changed[0].chosen == folds[0].chosen
    assert changed[0].training.fingerprint == folds[0].training.fingerprint
    with pytest.raises(ValueError, match="coverage"):
        walk_forward(
            sessions,
            (STRATEGY,),
            COST,
            train_size=2,
            test_size=1,
            min_bars_per_session=11,
        )
