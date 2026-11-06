"""Run only against the isolated disposable Compose test project."""

import secrets
from uuid import uuid4

import httpx
from sqlalchemy import delete

from app.auth import password_hasher
from app.database import SessionLocal
from app.models import User

email = f"smoke-{uuid4()}@example.test"
password = secrets.token_urlsafe(32)
with SessionLocal() as db:
    user = User(email=email, password_hash=password_hasher.hash(password))
    db.add(user)
    db.commit()
try:
    with httpx.Client(
        base_url="http://web", headers={"Origin": "http://web"}
    ) as client:
        assert client.get("/api/v1/health/ready").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/api/v1/instruments").status_code == 401
        result = client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert result.status_code == 200, result.text
        instruments = client.get("/api/v1/instruments").json()
        assert instruments["total"] == 7
        assert all(not i["execution_enabled"] for i in instruments["items"])
        assert all(i["provider_mappings"] for i in instruments["items"])
        assert client.get("/api/v1/system/status").json()["dependencies"] == {
            "database": "ok",
            "redis": "ok",
        }
        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401
    print(
        "Compose smoke passed: web proxy, readiness, login, instruments, status, logout"
    )
finally:
    with SessionLocal() as db:
        db.execute(delete(User).where(User.email == email))
        db.commit()
