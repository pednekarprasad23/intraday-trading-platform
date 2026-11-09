import os

from pytest import mark
from datetime import timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import main
from app.auth import password_hasher
from app.database import get_db
from app.models import Base, Instrument, User, utcnow


def test_utc_timestamp():
    assert utcnow().tzinfo == timezone.utc


@mark.skipif(
    os.getenv("AUTH_DISABLED", "false").lower() == "true",
    reason="Development mode: AUTH_DISABLED=true, production auth behavior tested separately",
)
def test_health_and_auth(tmp_path, monkeypatch):
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

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            User(
                email="admin@example.test",
                password_hash=password_hasher.hash("a-very-long-password"),
            )
        )
        db.add(
            Instrument(
                canonical_symbol="DEMO:NIFTY",
                display_name="NIFTY (DEMO)",
                asset_class="INDEX",
                exchange="NSE",
                segment="DEMO",
            )
        )
        db.commit()

    def db_override():
        with Session(engine) as db:
            yield db

    class FakeCache:
        def __init__(self):
            self.values = {}
            self.attempts = 0

        def incr(self, key):
            self.attempts += 1
            return self.attempts

        def expire(self, *args):
            pass

        def setex(self, key, ttl, value):
            self.values[key] = value.encode()

        def get(self, key):
            return self.values.get(key)

        def delete(self, key):
            self.values.pop(key, None)

    fake = FakeCache()
    monkeypatch.setattr("app.auth.cache", lambda: fake)
    main.app.dependency_overrides[get_db] = db_override
    try:
        with TestClient(main.app) as client:
            assert client.get("/api/v1/health/live").json() == {"status": "ok"}
            assert client.get("/api/v1/instruments").status_code == 401
            assert client.get("/api/v1/historical/imports").status_code == 401
            assert client.get("/api/v1/historical/partitions").status_code == 401
            assert (
                client.get(
                    "/api/v1/historical/imports/00000000-0000-0000-0000-000000000000/gaps"
                ).status_code
                == 401
            )
            assert (
                client.post(
                    "/api/v1/auth/login",
                    json={"email": "admin@example.test", "password": "wrong"},
                ).status_code
                == 401
            )
            login = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "admin@example.test",
                    "password": "a-very-long-password",
                },
            )
            assert login.status_code == 200
            assert "httponly" in login.headers["set-cookie"].lower()
            res = client.get("/api/v1/instruments?search=NIFTY")
            print("STATUS:", res.status_code, "JSON:", res.json())
            assert res.json()["total"] == 1
            assert client.get("/api/v1/historical/imports").json() == {
                "total": 0,
                "items": [],
            }
            assert client.get("/api/v1/historical/partitions").json() == {
                "total": 0,
                "items": [],
            }
            assert client.get("/api/v1/historical/imports?limit=101").status_code == 422
            assert (
                client.get("/api/v1/historical/partitions?offset=-1").status_code == 422
            )
            assert (
                client.get(
                    "/api/v1/historical/imports/00000000-0000-0000-0000-000000000000/gaps"
                ).status_code
                == 404
            )
            assert (
                client.get("/api/v1/system/status").json()["live_trading_enabled"]
                is False
            )
            assert client.get("/api/v1/instruments?limit=0").status_code == 422
            assert client.get("/api/v1/instruments?offset=1").json() == {
                "items": [],
                "total": 1,
            }
            assert (
                client.post(
                    "/api/v1/auth/logout", headers={"Origin": "https://evil.invalid"}
                ).status_code
                == 403
            )
            assert client.post("/api/v1/auth/logout").status_code == 200
            assert client.get("/api/v1/instruments").status_code == 401
            client.post(
                "/api/v1/auth/login",
                json={
                    "email": "admin@example.test",
                    "password": "a-very-long-password",
                },
            )
            fake.values.clear()  # Redis TTL expiration removes the server-side session.
            assert client.get("/api/v1/auth/me").status_code == 401
            fake.attempts = 10
            assert (
                client.post(
                    "/api/v1/auth/login",
                    json={"email": "admin@example.test", "password": "wrong"},
                ).status_code
                == 429
            )
    finally:
        main.app.dependency_overrides.clear()


def test_readiness_failure_and_success(monkeypatch):
    with TestClient(main.app) as client:
        monkeypatch.setattr(
            main,
            "dependency_health",
            lambda: {"database": "unavailable", "redis": "ok"},
        )
        assert client.get("/api/v1/health/ready").status_code == 503
        assert client.get("/api/v1/health/live").status_code == 200
        monkeypatch.setattr(
            main, "dependency_health", lambda: {"database": "ok", "redis": "ok"}
        )
        assert client.get("/api/v1/health/ready").status_code == 200
