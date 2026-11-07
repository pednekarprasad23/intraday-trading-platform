"""Coverage is a catalog view, not proof of a streaming market feed."""

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import main
from app.auth import require_user
from app.database import get_db
from app.models import (
    Base,
    HistoricalImportJob,
    HistoricalPartition,
    Instrument,
    ProviderSymbol,
)


def test_coverage_requires_auth_and_reports_only_actual_provider_sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'coverage.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        verified = Instrument(
            canonical_symbol="NIFTY:26000CE:EXAMPLE",
            display_name="Verified option mapping",
            asset_class="OPTION",
            exchange="NSE",
            segment="NFO",
            is_demo=False,
            metadata_source="DHAN",
        )
        demo = Instrument(
            canonical_symbol="DEMO:NIFTY",
            display_name="Illustrative NIFTY",
            asset_class="INDEX",
            exchange="NSE",
            segment="DEMO",
        )
        db.add_all([verified, demo])
        db.flush()
        now = datetime(2026, 11, 7, tzinfo=timezone.utc)
        db.add_all(
            [
                ProviderSymbol(
                    instrument_id=verified.id,
                    provider="DHAN",
                    provider_instrument_key="40095",
                    last_verified_at=now,
                ),
                ProviderSymbol(
                    instrument_id=verified.id,
                    provider="OTHER",
                    provider_instrument_key="OTHER-ID",
                ),
                ProviderSymbol(
                    instrument_id=demo.id,
                    provider="DEMO",
                    provider_instrument_key="DEMO:NIFTY",
                ),
            ]
        )
        job = HistoricalImportJob(
            provider="DHAN",
            provider_instrument_key="40095",
            instrument_id=verified.id,
            timeframe="1m",
            session_date=date(2026, 11, 6),
            source_sha256="a" * 64,
            requested_from=now,
            requested_to=now,
            status="COMPLETED",
        )
        db.add(job)
        db.flush()
        db.add(
            HistoricalPartition(
                job_id=job.id,
                provider="DHAN",
                instrument_id=verified.id,
                timeframe="1m",
                session_date=date(2026, 11, 6),
                relative_path="test/session.parquet",
                checksum_sha256="b" * 64,
                row_count=375,
            )
        )
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    main.app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(main.app) as client:
            assert client.get("/api/v1/market/coverage").status_code == 401
            main.app.dependency_overrides[require_user] = lambda: object()
            assert client.get("/api/v1/market/coverage?limit=101").status_code == 422
            assert client.get("/api/v1/market/coverage?offset=-1").status_code == 422
            assert client.get("/api/v1/market/coverage?provider=dhan").json()["total"] == 1
            assert client.get("/api/v1/market/coverage?historical=false").json()["total"] == 2
            assert client.get("/api/v1/market/coverage?search=OTHER-ID").json()["total"] == 1
            response = client.get("/api/v1/market/coverage?limit=2")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3 and len(data["items"]) == 2
            assert data["live_feed_status"] == "unavailable"
            assert all(not item["live_quote_available"] for item in data["items"])
            remaining = client.get("/api/v1/market/coverage?offset=2").json()
            assert remaining["total"] == 3 and len(remaining["items"]) == 1
            all_items = data["items"] + remaining["items"]
            dhan = next(item for item in all_items if item["provider"] == "DHAN")
            assert dhan["demo"] is False
            assert dhan["historical_partition_count"] == 1
            assert dhan["latest_historical_session"] == "2026-11-06"
            assert dhan["execution_enabled"] is False
            other = next(item for item in all_items if item["provider"] == "OTHER")
            assert other["historical_partition_count"] == 0
            assert other["latest_historical_session"] is None
            assert (
                next(item for item in all_items if item["provider"] == "DEMO")["demo"]
                is True
            )
            assert client.post("/api/v1/market/coverage").status_code == 405
    finally:
        main.app.dependency_overrides.clear()
