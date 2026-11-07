from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.historical.importer import import_fixture
from app.models import StrategySignal, StrategyVersion
from app.strategies.contracts import Candle, Source, StrategyConfig
from app.strategies.engine import evaluate
from app.strategies.indicators import atr, ema, rsi, vwap
from app.strategy_evaluation import evaluate_fixture
from tests.test_historical import setup_db

D = Decimal
CONFIG = StrategyConfig("option-premium-ema-rsi", 1, 2, 3, 2, D("40"), D("100"))


def sample(n=5):
    start = datetime(2026, 11, 6, 3, 45, tzinfo=timezone.utc)
    return tuple(
        Candle(
            start + timedelta(minutes=i),
            D(10 + i),
            D(11 + i),
            D(9 + i),
            D(10 + i),
            D(1),
        )
        for i in range(n)
    )


def source():
    return Source(
        uuid4(),
        "DEMO",
        "OPT",
        uuid4(),
        "a" * 64,
        "b" * 64,
        date(2026, 11, 6),
        "1m",
        date(2030, 12, 31),
        "CE",
    )


def test_repeatable_signal_and_window_quality():
    bars = sample()
    first = evaluate(CONFIG, source(), bars)
    assert first == evaluate(CONFIG, first.source, bars)
    assert (first.direction, first.quality, first.decision_time) == (
        "LONG",
        "VALID",
        bars[-1].bar_time + timedelta(minutes=1),
    )
    assert evaluate(CONFIG, first.source, bars[:2]).reasons == ("INSUFFICIENT_HISTORY",)
    gap = bars[:2] + bars[3:]
    assert evaluate(CONFIG, first.source, gap).reasons == ("GAP_OR_DUPLICATE",)
    assert evaluate(
        CONFIG,
        first.source,
        bars[:-1] + (Candle(bars[-1].bar_time, D(14), D(15), D(13), D(14), None),),
    ).reasons == ("MISSING_VOLUME",)
    with pytest.raises(ValueError, match="Unsupported"):
        evaluate(
            StrategyConfig("unknown", 1, 2, 3, 2, D(40), D(100)), first.source, bars
        )
    with pytest.raises(ValueError, match="EMA periods"):
        evaluate(
            StrategyConfig(CONFIG.strategy_id, 1, 3, 3, 2, D(40), D(100)),
            first.source,
            bars,
        )
    with pytest.raises(ValueError, match="Window"):
        evaluate(CONFIG, first.source, bars * 101)


def test_indicators_warmup_denominators_and_utc():
    bars = sample()
    assert ema((D(1),), 2) is None
    assert ema((D(1), D(2), D(3)), 2) == D("2.5")
    assert rsi((D(1), D(1), D(1)), 2) == D(50)
    assert rsi((D(1), D(2), D(3)), 2) == D(100)
    assert atr(bars[:2], 2) is None
    assert atr(bars, 2) == D(2)
    assert vwap(bars) == D(12)
    assert (
        vwap(
            tuple(
                Candle(b.bar_time, b.open, b.high, b.low, b.close, D(0)) for b in bars
            )
        )
        is None
    )
    with pytest.raises(ValueError, match="aware"):
        Candle(datetime(2026, 11, 6), D(1), D(1), D(1), D(1), D(1))
    with pytest.raises(ValueError, match="Decimal"):
        Candle(bars[0].bar_time, 1.0, D(1), D(1), D(1), D(1))


def test_operator_revalidates_fixture_and_persists_exact_inputs(tmp_path):
    engine, _ = setup_db(tmp_path)
    fixture = tmp_path / "complete.csv"
    start = datetime(2026, 11, 6, 3, 45, tzinfo=timezone.utc)
    fixture.write_text(
        "bar_time,open,high,low,close,volume\n"
        + "".join(
            f"{(start + timedelta(minutes=i)).isoformat()},{10 + i},{11 + i},{9 + i},{10 + i},1\n"
            for i in range(5)
        ),
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
            session_start=datetime.min.time().replace(hour=9, minute=15),
            session_end=datetime.min.time().replace(hour=9, minute=20),
            source_sha256=sha256(fixture.read_bytes()).hexdigest(),
        )
        db.commit()
        decision = evaluate_fixture(
            db, fixture, job_id=job.id, config=CONFIG, root=tmp_path / "parquet"
        )
        db.commit()
        signal = db.scalar(select(StrategySignal))
        assert (
            decision.direction == "LONG"
            and signal.snapshot["window"][-1]["close"] == "14"
        )
        assert signal.snapshot["source"]["source_sha256"] == job.source_sha256
        assert len(db.scalars(select(StrategyVersion)).all()) == 1
        assert (
            evaluate_fixture(
                db, fixture, job_id=job.id, config=CONFIG, root=tmp_path / "parquet"
            )
            == decision
        )
        assert len(db.scalars(select(StrategySignal)).all()) == 1
        partition_file = next((tmp_path / "parquet").rglob("*.parquet"))
        original = partition_file.read_bytes()
        partition_file.write_bytes(b"tampered")
        with pytest.raises(ValueError, match="Partition checksum"):
            evaluate_fixture(
                db, fixture, job_id=job.id, config=CONFIG, root=tmp_path / "parquet"
            )
        partition_file.write_bytes(original)
        fixture.write_text(fixture.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="checksum"):
            evaluate_fixture(
                db, fixture, job_id=job.id, config=CONFIG, root=tmp_path / "parquet"
            )
        assert len(db.scalars(select(StrategySignal)).all()) == 1


def test_operator_rejects_imported_gap(tmp_path):
    engine, _ = setup_db(tmp_path)
    fixture = Path(__file__).parent / "fixtures" / "DEMO_option_1m.csv"
    with Session(engine) as db:
        job = import_fixture(
            db,
            fixture,
            tmp_path / "parquet",
            provider="DEMO",
            provider_key="OPT100CE",
            timeframe="1m",
            session_date=date(2026, 11, 6),
            session_start=datetime.min.time().replace(hour=9, minute=15),
            session_end=datetime.min.time().replace(hour=9, minute=18),
            source_sha256=sha256(fixture.read_bytes()).hexdigest(),
        )
        db.commit()
        with pytest.raises(ValueError, match="GAP"):
            evaluate_fixture(
                db, fixture, job_id=job.id, config=CONFIG, root=tmp_path / "parquet"
            )
        assert db.scalar(select(StrategySignal)) is None


def test_strategy_package_has_no_execution_or_provider_imports():
    root = Path(__file__).parents[1] / "app" / "strategies"
    for module in root.glob("*.py"):
        text = module.read_text(encoding="utf-8")
        assert "app.providers" not in text and "app.market_data" not in text
        assert "app.orders" not in text and "importlib" not in text
