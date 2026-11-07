from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import main
from app.backtesting.engine import run
from app.backtesting.reports import persist_backtest, persist_walk_forward
from app.backtesting.walk_forward import walk_forward
from app.database import get_db
from app.historical.importer import import_fixture
from app.models import BacktestReport, ResearchEvaluation, WalkForwardReport
from app.strategy_evaluation import evaluate_catalog, evaluate_fixture
from tests.test_strategies import CONFIG
from tests.test_backtesting import COST, STRATEGY, catalog, load
from tests.test_historical import setup_db


def test_operator_evaluation_history_includes_none_without_replay_duplication(tmp_path):
    engine, _ = setup_db(tmp_path)
    fixture = tmp_path / "flat.csv"
    start = datetime(2026, 11, 6, 3, 45, tzinfo=timezone.utc)
    fixture.write_text(
        "bar_time,open,high,low,close,volume\n"
        + "".join(
            f"{(start + timedelta(minutes=i)).isoformat()},10,11,9,10,1\n"
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
            session_start=time(9, 15),
            session_end=time(9, 20),
            source_sha256=sha256(fixture.read_bytes()).hexdigest(),
        )
        db.commit()
        first = evaluate_fixture(
            db, fixture, job_id=job.id, config=CONFIG, root=tmp_path / "parquet"
        )
        db.commit()
        assert first.direction == "NONE"
        assert (
            evaluate_fixture(
                db, fixture, job_id=job.id, config=CONFIG, root=tmp_path / "parquet"
            )
            == first
        )
        db.commit()
        records = db.scalars(select(ResearchEvaluation)).all()
        assert (
            len(records) == 1
            and records[0].quality == "VALID"
            and records[0].direction == "NONE"
        )
        from app.models import HistoricalPartition

        partition = db.scalar(
            select(HistoricalPartition).where(HistoricalPartition.job_id == job.id)
        )
        from app.models import Instrument

        db.get(Instrument, job.instrument_id).underlying_id = job.instrument_id
        db.flush()
        catalog_decision = evaluate_catalog(
            db,
            root=tmp_path / "parquet",
            instrument_id=job.instrument_id,
            provider="DEMO",
            timeframe="1m",
            session_date=date(2026, 11, 6),
            config=CONFIG,
        )
        assert catalog_decision == first
        assert partition is not None
        assert len(db.scalars(select(ResearchEvaluation)).all()) == 1
        db.commit()

    def db_override():
        with Session(engine) as db:
            yield db

    from app.auth import require_user

    main.app.dependency_overrides[get_db] = db_override
    main.app.dependency_overrides[require_user] = lambda: object()
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/v1/research/evaluations?limit=1")
            assert response.status_code == 200
            assert response.json()["items"][0]["direction"] == "NONE"
            assert response.json()["items"][0]["demo"] is True
            assert (
                client.get("/api/v1/research/evaluations?limit=101").status_code == 422
            )
            assert (
                client.get("/api/v1/research/evaluations?offset=-1").status_code == 422
            )
    finally:
        main.app.dependency_overrides.clear()


def test_persisted_research_is_deduplicated_and_safe(tmp_path):
    engine, root, instrument_id, dates = catalog(tmp_path)
    sessions = load(engine, root, instrument_id, dates)
    result = run(sessions, STRATEGY, COST)
    folds = walk_forward(
        sessions,
        (STRATEGY, replace(STRATEGY, rsi_floor=STRATEGY.rsi_floor + 1)),
        COST,
        train_size=2,
        test_size=1,
    )
    with Session(engine) as db:
        backtest = persist_backtest(db, sessions, STRATEGY, COST, result)
        walk = persist_walk_forward(db, sessions, STRATEGY, COST, folds, 2, 1)
        db.commit()
        assert persist_backtest(db, sessions, STRATEGY, COST, result).id == backtest.id
        assert (
            persist_walk_forward(db, sessions, STRATEGY, COST, folds, 2, 1).id
            == walk.id
        )
        assert len(db.scalars(select(BacktestReport)).all()) == 1
        assert len(db.scalars(select(WalkForwardReport)).all()) == 1
        assert backtest.metrics["net_pnl"] == str(result.metrics.net_pnl)
        assert len(walk.folds) == 2
        assert "relative_path" not in str(backtest.trade_summary)

    def db_override():
        with Session(engine) as db:
            yield db

    main.app.dependency_overrides[get_db] = db_override
    try:
        with TestClient(main.app) as client:
            for path in ("signals", "evaluations", "backtests", "walk-forwards"):
                assert client.get(f"/api/v1/research/{path}").status_code == 401
            # Bypass only auth for these read-route tests; login/session behavior is tested separately.
            from app.auth import require_user

            main.app.dependency_overrides[require_user] = lambda: object()
            assert client.get("/api/v1/research/signals").json() == {
                "total": 0,
                "items": [],
            }
            assert client.get("/api/v1/research/evaluations").json() == {
                "total": 0,
                "items": [],
            }
            for path in ("backtests", "walk-forwards"):
                assert (
                    client.get(f"/api/v1/research/{path}?limit=101").status_code == 422
                )
                assert (
                    client.get(f"/api/v1/research/{path}?offset=-1").status_code == 422
                )
                page = client.get(f"/api/v1/research/{path}?limit=1").json()
                assert page["total"] == 1 and len(page["items"]) == 1
                assert "NO BROKER ORDER" in page["items"][0]["label"]
                assert "simulation_config" not in page["items"][0]
                assert (
                    client.get(f"/api/v1/research/{path}?offset=1").json()["items"]
                    == []
                )
            detail = client.get(f"/api/v1/research/backtests/{backtest.id}").json()
            assert detail["metrics"]["net_pnl"] == str(result.metrics.net_pnl)
            assert "trade_summary" in detail and "relative_path" not in str(detail)
            assert (
                len(
                    client.get(f"/api/v1/research/walk-forwards/{walk.id}").json()[
                        "folds"
                    ]
                )
                == 2
            )
            assert client.post("/api/v1/research/backtests").status_code == 405
    finally:
        main.app.dependency_overrides.clear()
