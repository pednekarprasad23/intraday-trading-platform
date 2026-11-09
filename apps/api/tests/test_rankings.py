"""Integration tests for the rankings API routes."""

import os
from uuid import uuid4

from pytest import mark
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import main
from app.auth import require_user
from app.database import get_db
from app.models import BacktestReport, Instrument
from tests.test_historical import setup_db


def _insert_backtest(db, instrument_id, metrics, strategy_id="test-strategy", strategy_version=1):
    report = BacktestReport(
        fingerprint=f"fp_{uuid4().hex[:16]}",
        input_fingerprint=f"inp_{uuid4().hex[:16]}",
        provider="DHAN",
        instrument_id=instrument_id,
        timeframe="1m",
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        simulation_config={"quantity": "1"},
        strategy_config={"strategy_id": strategy_id},
        sources=[{"session_date": "2026-11-06"}],
        metrics=metrics,
        warnings=[],
        trade_summary=[],
        event_summary=[],
    )
    db.add(report)


def _insert_reports(db, instrument_id):
    # Good candidate
    _insert_backtest(db, instrument_id, {
        "net_pnl": "500", "win_rate": "0.6", "profit_factor": "2.0",
        "max_drawdown": "50", "longest_losing_streak": "3", "trade_count": 20,
    }, "good-strategy")
    # Rejected candidate
    _insert_backtest(db, instrument_id, {
        "net_pnl": "100", "win_rate": "0.2", "profit_factor": "0.5",
        "max_drawdown": "80", "longest_losing_streak": "10", "trade_count": 2,
    }, "bad-strategy")
    # Another good candidate with different strategy
    _insert_backtest(db, instrument_id, {
        "net_pnl": "800", "win_rate": "0.7", "profit_factor": "3.0",
        "max_drawdown": "30", "longest_losing_streak": "2", "trade_count": 30,
    }, "other-strategy")


def _make_db_override(engine):
    def db_override():
        with Session(engine) as db:
            yield db
    return db_override


class TestRankingsAuth:
    @mark.skipif(
        os.getenv("AUTH_DISABLED", "false").lower() == "true",
        reason="Development mode: AUTH_DISABLED=true, production auth behavior tested separately",
    )
    def test_requires_auth(self, tmp_path, monkeypatch):
        from app.config import get_settings
        orig_settings = get_settings()
        class ProdSettings:
            app_env = "production"
            auth_disabled = False
            redis_url = orig_settings.redis_url
            database_url = orig_settings.database_url
            session_ttl_seconds = orig_settings.session_ttl_seconds
            mt5_snapshot_path = orig_settings.mt5_snapshot_path
            angelone_snapshot_path = orig_settings.angelone_snapshot_path
            angelone_enabled = orig_settings.angelone_enabled
            historical_data_root = orig_settings.historical_data_root
            credential_key_path = orig_settings.credential_key_path
            app_name = orig_settings.app_name
            app_version = orig_settings.app_version
        monkeypatch.setattr("app.auth.get_settings", lambda: ProdSettings())
        monkeypatch.setattr("app.main.get_settings", lambda: ProdSettings())

        engine, _ = setup_db(tmp_path)
        with Session(engine) as db:
            instrument_id = uuid4()
            db.add(Instrument(
                id=instrument_id, canonical_symbol="TEST", display_name="Test",
                asset_class="INDEX", exchange="NSE", segment="INDEX", is_demo=True,
            ))
            db.commit()
        main.app.dependency_overrides[get_db] = _make_db_override(engine)
        try:
            with TestClient(main.app) as client:
                resp = client.get("/api/v1/research/rankings")
                assert resp.status_code == 401
        finally:
            main.app.dependency_overrides.clear()


class TestRankingsList:
    def test_empty_db(self, tmp_path):
        engine, _ = setup_db(tmp_path)
        main.app.dependency_overrides[get_db] = _make_db_override(engine)
        main.app.dependency_overrides[require_user] = lambda: object()
        try:
            with TestClient(main.app) as client:
                resp = client.get("/api/v1/research/rankings")
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 0
                assert data["items"] == []
        finally:
            main.app.dependency_overrides.clear()

    def test_returns_ranked_list(self, tmp_path):
        engine, _ = setup_db(tmp_path)
        with Session(engine) as db:
            instrument_id = uuid4()
            db.add(Instrument(
                id=instrument_id, canonical_symbol="TEST", display_name="Test",
                asset_class="INDEX", exchange="NSE", segment="INDEX", is_demo=True,
            ))
            _insert_reports(db, instrument_id)
            db.commit()

        main.app.dependency_overrides[get_db] = _make_db_override(engine)
        main.app.dependency_overrides[require_user] = lambda: object()
        try:
            with TestClient(main.app) as client:
                resp = client.get("/api/v1/research/rankings")
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 3
                assert len(data["items"]) == 3
                # Verify descending order
                scores = [item["composite_score"] for item in data["items"]]
                assert scores == sorted(scores, reverse=True)
        finally:
            main.app.dependency_overrides.clear()

    def test_rejected_only_filter(self, tmp_path):
        engine, _ = setup_db(tmp_path)
        with Session(engine) as db:
            instrument_id = uuid4()
            db.add(Instrument(
                id=instrument_id, canonical_symbol="TEST", display_name="Test",
                asset_class="INDEX", exchange="NSE", segment="INDEX", is_demo=True,
            ))
            _insert_reports(db, instrument_id)
            db.commit()

        main.app.dependency_overrides[get_db] = _make_db_override(engine)
        main.app.dependency_overrides[require_user] = lambda: object()
        try:
            with TestClient(main.app) as client:
                resp = client.get("/api/v1/research/rankings?rejected_only=true")
                assert resp.status_code == 200
                data = resp.json()
                for item in data["items"]:
                    assert item["is_rejected"] is True
        finally:
            main.app.dependency_overrides.clear()

    def test_strategy_filter(self, tmp_path):
        engine, _ = setup_db(tmp_path)
        with Session(engine) as db:
            instrument_id = uuid4()
            db.add(Instrument(
                id=instrument_id, canonical_symbol="TEST", display_name="Test",
                asset_class="INDEX", exchange="NSE", segment="INDEX", is_demo=True,
            ))
            _insert_reports(db, instrument_id)
            db.commit()

        main.app.dependency_overrides[get_db] = _make_db_override(engine)
        main.app.dependency_overrides[require_user] = lambda: object()
        try:
            with TestClient(main.app) as client:
                resp = client.get("/api/v1/research/rankings?strategy_id=good-strategy")
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert data["items"][0]["strategy_id"] == "good-strategy"
        finally:
            main.app.dependency_overrides.clear()

    def test_pagination(self, tmp_path):
        engine, _ = setup_db(tmp_path)
        with Session(engine) as db:
            instrument_id = uuid4()
            db.add(Instrument(
                id=instrument_id, canonical_symbol="TEST", display_name="Test",
                asset_class="INDEX", exchange="NSE", segment="INDEX", is_demo=True,
            ))
            _insert_reports(db, instrument_id)
            db.commit()

        main.app.dependency_overrides[get_db] = _make_db_override(engine)
        main.app.dependency_overrides[require_user] = lambda: object()
        try:
            with TestClient(main.app) as client:
                resp = client.get("/api/v1/research/rankings?limit=1&offset=0")
                data = resp.json()
                assert data["total"] == 3
                assert len(data["items"]) == 1

                resp2 = client.get("/api/v1/research/rankings?limit=1&offset=2")
                data2 = resp2.json()
                assert len(data2["items"]) == 1
                assert data2["items"][0]["candidate_id"] != data["items"][0]["candidate_id"]
        finally:
            main.app.dependency_overrides.clear()

    def test_response_structure(self, tmp_path):
        engine, _ = setup_db(tmp_path)
        with Session(engine) as db:
            instrument_id = uuid4()
            db.add(Instrument(
                id=instrument_id, canonical_symbol="TEST", display_name="Test",
                asset_class="INDEX", exchange="NSE", segment="INDEX", is_demo=True,
            ))
            _insert_backtest(db, instrument_id, {
                "net_pnl": "500", "win_rate": "0.6", "profit_factor": "2.0",
                "max_drawdown": "50", "longest_losing_streak": "3", "trade_count": 20,
            })
            db.commit()

        main.app.dependency_overrides[get_db] = _make_db_override(engine)
        main.app.dependency_overrides[require_user] = lambda: object()
        try:
            with TestClient(main.app) as client:
                resp = client.get("/api/v1/research/rankings")
                data = resp.json()
                item = data["items"][0]
                # Verify all expected fields
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
                # Verify RESEARCH ONLY label in commentary
                assert "RESEARCH ONLY" in item["commentary"]
        finally:
            main.app.dependency_overrides.clear()


class TestLatestRankings:
    def test_deduplicates(self, tmp_path):
        engine, _ = setup_db(tmp_path)
        with Session(engine) as db:
            instrument_id = uuid4()
            db.add(Instrument(
                id=instrument_id, canonical_symbol="TEST", display_name="Test",
                asset_class="INDEX", exchange="NSE", segment="INDEX", is_demo=True,
            ))
            # Same strategy, different dates → should deduplicate
            _insert_backtest(db, instrument_id, {
                "net_pnl": "500", "win_rate": "0.6", "profit_factor": "2.0",
                "max_drawdown": "50", "longest_losing_streak": "3", "trade_count": 20,
            }, "same-strategy", 1)
            _insert_backtest(db, instrument_id, {
                "net_pnl": "800", "win_rate": "0.7", "profit_factor": "3.0",
                "max_drawdown": "30", "longest_losing_streak": "2", "trade_count": 30,
            }, "same-strategy", 1)
            db.commit()

        main.app.dependency_overrides[get_db] = _make_db_override(engine)
        main.app.dependency_overrides[require_user] = lambda: object()
        try:
            with TestClient(main.app) as client:
                resp = client.get("/api/v1/research/rankings/latest")
                data = resp.json()
                assert data["total"] == 1
        finally:
            main.app.dependency_overrides.clear()
