import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.market_data.mt5 import read_snapshot


def test_snapshot_fails_closed_and_expires(tmp_path, monkeypatch):
    settings = get_settings()
    path = tmp_path / "snapshot.json"
    monkeypatch.setattr(settings, "mt5_snapshot_path", str(path))
    assert read_snapshot()["quality"] == "UNAVAILABLE"
    now = datetime.now(timezone.utc)
    data = {
        "observed_at": now.isoformat(),
        "status": {
            "connected": True,
            "orders_available": False,
            "provenance": "MT5_TERMINAL",
            "observed_at": now.isoformat(),
        },
        "account": None,
        "positions": [],
        "history": [],
        "quotes": [],
        "errors": ["account unavailable"],
    }
    path.write_text(json.dumps(data))
    assert read_snapshot()["quality"] == "FRESH"
    assert read_snapshot()["snapshot"]["positions"] == []
    data["observed_at"] = (now - timedelta(seconds=46)).isoformat()
    path.write_text(json.dumps(data))
    assert read_snapshot()["quality"] == "STALE"
    assert read_snapshot()["snapshot"] is None
    data["observed_at"] = now.isoformat()
    data["login"] = "private"
    path.write_text(json.dumps(data))
    assert read_snapshot()["quality"] == "UNAVAILABLE"
    path.write_text("{broken")
    assert read_snapshot()["quality"] == "UNAVAILABLE"


def test_snapshot_requires_session():
    with TestClient(app) as client:
        assert client.get("/api/v1/mt5/snapshot").status_code == 401
