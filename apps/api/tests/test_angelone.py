import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.market_data.angelone import read_snapshot
from app.providers.angelone.readonly import AngelOneReadOnlyClient


def test_read_only_ltp_normalization_rejects_unknown_and_invalid():
    instrument = uuid4()
    now = datetime.now(timezone.utc)
    client = AngelOneReadOnlyClient({"123": instrument})
    quote = client.normalize_ltp("123", "100.25", now, now)
    assert quote.last_price == 100.25
    assert quote.provenance == "BROKER_FIXTURE"
    with pytest.raises(ValueError, match="Unknown"):
        client.normalize_ltp("999", "100", now, now)
    with pytest.raises(ValueError):
        client.normalize_ltp("123", "NaN", now, now)
    with pytest.raises(ValueError):
        client.normalize_ltp("123", "1", now.replace(tzinfo=None), now)


@pytest.mark.skipif(
    os.getenv("AUTH_DISABLED", "false").lower() == "true",
    reason="Development mode: AUTH_DISABLED=true, production auth behavior tested separately",
)
def test_angel_snapshot_is_protected_and_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "false")
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    settings = get_settings()
    path = tmp_path / "angel.json"
    monkeypatch.setattr(settings, "angelone_snapshot_path", str(path))
    monkeypatch.setattr(settings, "angelone_enabled", False)
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/angelone/snapshot").status_code == 401
    finally:
        get_settings.cache_clear()
    now = datetime.now(timezone.utc).isoformat()
    path.write_text(
        json.dumps(
            {
                "observed_at": now,
                "provider": "ANGEL_ONE",
                "authenticated": True,
                "quotes": [],
                "errors": [],
                "orders_available": False,
            }
        )
    )
    assert read_snapshot()["quality"] == "UNAVAILABLE"
    monkeypatch.setenv("ANGELONE_ENABLED", "true")
    monkeypatch.setenv("ANGELONE_SNAPSHOT_PATH", str(path))
    get_settings.cache_clear()
    now = datetime.now(timezone.utc).isoformat()
    path.write_text(
        json.dumps(
            {
                "observed_at": now,
                "provider": "ANGEL_ONE",
                "authenticated": True,
                "quotes": [],
                "errors": [],
                "orders_available": False,
            }
        )
    )
    assert read_snapshot()["quality"] == "UNVERIFIED"
    data = json.loads(path.read_text())
    data["quotes"] = [
        {
            "symbol": "TEST",
            "ltp": "100.25",
            "event_time": None,
            "received_at": now,
            "provenance": "ANGEL_ONE",
        }
    ]
    path.write_text(json.dumps(data))
    assert (
        read_snapshot()["snapshot"]["quotes"][0]["quality"] == "UNVERIFIED_EVENT_TIME"
    )
    data["quotes"][0]["ltp"] = "NaN"
    path.write_text(json.dumps(data))
    assert read_snapshot()["quality"] == "UNAVAILABLE"
    with TestClient(app) as client:
        assert client.get("/api/v1/angelone/snapshot").status_code == 401
    path.write_text("{broken")
    assert read_snapshot()["quality"] == "UNAVAILABLE"
