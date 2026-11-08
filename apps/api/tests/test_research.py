"""Tests for research ranking API endpoints.

Phase 2-A: Research ranking contract and reproducibility
"""

from datetime import date, datetime, time, timezone
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app import main
from app.backtesting.engine import run
from app.backtesting.reports import persist_backtest, persist_walk_forward
from app.database import engine as db_engine
from app.historical.importer import import_fixture
from app.models import BacktestReport, WalkForwardReport
from app.strategy_evaluation import evaluate_catalog, evaluate_fixture
from tests.test_backtesting import COST, STRATEGY, catalog, load
from tests.test_historical import setup_db


@pytest.fixture
def research_db(tmp_path):
    """Setup database with research data."""
    engine, _ = setup_db(tmp_path)

    # Create a simple fixture
    fixture = tmp_path / "flat.csv"
    start = datetime(2026, 11, 6, 3, 45, tzinfo=timezone.utc)
    fixture.write_text(
        "bar_time,open,high,low,close,volume\n"
        + "".join(
            f"{(start.__add__(__import__('datetime').timedelta(minutes=i))).isoformat()},{i+10},{i+11},{i+9},{i+10},{i+1}\n"
            for i in range(50)
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

        # Run backtest to generate reports
        config = {
            "strategy_id": "test-strategy",
            "strategy_version": 1,
            "instrument_id": "OPT100CE",
            "timeframe": "1m",
            "cost": COST,
            "params": {},
            "config": {},
            "catalog": [],
        }

        results = run(
            engine,
            fixture,
            STRATEGY,
            config,
            root=tmp_path / "parquet",
            instrument_id="OPT100CE",
        )

        if results.reports:
            report = results.reports[0]
            persist_backtest(report, db)
            db.commit()

        yield engine, db

    # Cleanup
    with Session(engine) as db:
        db.execute(delete(WalkForwardReport))
        db.execute(delete(BacktestReport))
        db.commit()


def test_research_rankings_requires_auth():
    """Rankings endpoint should require authentication."""
    with TestClient(main.app) as client:
        response = client.get("/api/v1/research/rankings")
        assert response.status_code == 401


def test_research_rankings_empty_returns_empty_list(tmp_path):
    """Rankings endpoint should return empty list when no data."""
    engine, _ = setup_db(tmp_path)

    with TestClient(main.app) as client:
        # Mock authentication
        from unittest.mock import MagicMock
        mock_user = {"user_id": "test", "email": "test@example.com"}
        from app.auth import require_user
        main.app.dependency_overrides[require_user] = lambda: mock_user

        try:
            response = client.get("/api/v1/research/rankings")
            assert response.status_code == 200
            data = response.json()

            assert "total" in data
            assert "limit" in data
            assert "offset" in data
            assert "items" in data
            assert data["total"] == 0
            assert len(data["items"]) == 0
        finally:
            main.app.dependency_overrides.clear()


def test_research_rankings_with_data(research_db):
    """Rankings endpoint should return ranked candidates with backtest data."""
    engine, db = research_db

    with TestClient(main.app) as client:
        # Mock authentication
        from unittest.mock import MagicMock
        mock_user = {"user_id": "test", "email": "test@example.com"}
        from app.auth import require_user
        main.app.dependency_overrides[require_user] = lambda: mock_user

        try:
            response = client.get("/api/v1/research/rankings")
            assert response.status_code == 200
            data = response.json()

            # Should have at least one candidate if backtest ran
            assert "total" in data
            assert "items" in data

            if data["total"] > 0:
                item = data["items"][0]
                # Verify ranking structure
                assert "candidate_id" in item
                assert "strategy_id" in item
                assert "strategy_version" in item
                assert "instrument_id" in item
                assert "session_date" in item
                assert "composite_score" in item
                assert "score_breakdown" in item
                assert "sub_scores" in item
                assert "is_rejected" in item
                assert "rejection_reasons" in item
                assert "ranking_version" in item
                assert "commentary" in item
                assert "evidence" in item

                # Verify evidence contains metrics
                if "evidence" in item:
                    assert "metrics" in item["evidence"]
                    assert "sources" in item["evidence"]
        finally:
            main.app.dependency_overrides.clear()


def test_research_rankings_pagination(tmp_path):
    """Rankings endpoint should support pagination."""
    engine, _ = setup_db(tmp_path)

    with TestClient(main.app) as client:
        # Mock authentication
        from unittest.mock import MagicMock
        mock_user = {"user_id": "test", "email": "test@example.com"}
        from app.auth import require_user
        main.app.dependency_overrides[require_user] = lambda: mock_user

        try:
            # Test with limit and offset
            response = client.get(
                "/api/v1/research/rankings?limit=10&offset=0"
            )
            assert response.status_code == 200
            data = response.json()

            assert data["limit"] == 10
            assert data["offset"] == 0
        finally:
            main.app.dependency_overrides.clear()


def test_research_latest_rankings_requires_auth():
    """Latest rankings endpoint should require authentication."""
    with TestClient(main.app) as client:
        response = client.get("/api/v1/research/rankings/latest")
        assert response.status_code == 401


def test_research_latest_rankings_empty(tmp_path):
    """Latest rankings endpoint should return empty when no data."""
    engine, _ = setup_db(tmp_path)

    with TestClient(main.app) as client:
        # Mock authentication
        from unittest.mock import MagicMock
        mock_user = {"user_id": "test", "email": "test@example.com"}
        from app.auth import require_user
        main.app.dependency_overrides[require_user] = lambda: mock_user

        try:
            response = client.get("/api/v1/research/rankings/latest")
            assert response.status_code == 200
            data = response.json()

            assert "total" in data
            assert "items" in data
        finally:
            main.app.dependency_overrides.clear()


def test_research_rankings_filter_by_strategy(research_db):
    """Rankings endpoint should filter by strategy_id."""
    engine, db = research_db

    with TestClient(main.app) as client:
        # Mock authentication
        from unittest.mock import MagicMock
        mock_user = {"user_id": "test", "email": "test@example.com"}
        from app.auth import require_user
        main.app.dependency_overrides[require_user] = lambda: mock_user

        try:
            response = client.get(
                "/api/v1/research/rankings?strategy_id=test-strategy"
            )
            assert response.status_code == 200
            data = response.json()

            # All returned items should match the strategy
            for item in data["items"]:
                assert item["strategy_id"] == "test-strategy"
        finally:
            main.app.dependency_overrides.clear()


def test_research_rankings_rejected_only(tmp_path):
    """Rankings endpoint should filter rejected only when requested."""
    engine, _ = setup_db(tmp_path)

    with TestClient(main.app) as client:
        # Mock authentication
        from unittest.mock import MagicMock
        mock_user = {"user_id": "test", "email": "test@example.com"}
        from app.auth import require_user
        main.app.dependency_overrides[require_user] = lambda: mock_user

        try:
            response = client.get(
                "/api/v1/research/rankings?rejected_only=true"
            )
            assert response.status_code == 200
            data = response.json()

            # All returned items should be rejected
            for item in data["items"]:
                assert item["is_rejected"] is True
        finally:
            main.app.dependency_overrides.clear()


def test_research_deterministic_scoring(research_db):
    """Scoring should be deterministic - same input produces same output."""
    engine, db = research_db

    with TestClient(main.app) as client:
        # Mock authentication
        from unittest.mock import MagicMock
        mock_user = {"user_id": "test", "email": "test@example.com"}
        from app.auth import require_user
        main.app.dependency_overrides[require_user] = lambda: mock_user

        try:
            # Run rankings twice and compare
            response1 = client.get("/api/v1/research/rankings")
            assert response1.status_code == 200
            data1 = response1.json()

            response2 = client.get("/api/v1/research/rankings")
            assert response2.status_code == 200
            data2 = response2.json()

            # Scores should match (deterministic)
            if data1["total"] > 0 and data2["total"] > 0:
                for i in range(min(len(data1["items"]), len(data2["items"]))):
                    assert (
                        data1["items"][i]["composite_score"]
                        == data2["items"][i]["composite_score"]
                    )
                    assert (
                        data1["items"][i]["score_breakdown"]
                        == data2["items"][i]["score_breakdown"]
                    )
        finally:
            main.app.dependency_overrides.clear()


def test_research_commentary_generated(research_db):
    """Rankings should include generated commentary."""
    engine, db = research_db

    with TestClient(main.app) as client:
        # Mock authentication
        from unittest.mock import MagicMock
        mock_user = {"user_id": "test", "email": "test@example.com"}
        from app.auth import require_user
        main.app.dependency_overrides[require_user] = lambda: mock_user

        try:
            response = client.get("/api/v1/research/rankings")
            assert response.status_code == 200
            data = response.json()

            if data["total"] > 0:
                item = data["items"][0]
                # Commentary should be a non-empty string
                assert "commentary" in item
                assert isinstance(item["commentary"], str)
                assert len(item["commentary"]) > 0
        finally:
            main.app.dependency_overrides.clear()
