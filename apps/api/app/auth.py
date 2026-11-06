import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AuditLog, User

router = APIRouter(prefix="/api/v1/auth")
password_hasher = PasswordHasher()
# A dummy hash prevents a missing username from bypassing password hashing cost.
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def cache():
    return Redis.from_url(
        get_settings().redis_url, socket_timeout=2, socket_connect_timeout=2
    )


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


def require_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(401, "Authentication required")
    try:
        user_id = cache().get("session:" + hashlib.sha256(token.encode()).hexdigest())
    except Exception:
        raise HTTPException(503, "Session service unavailable") from None
    user = (
        db.scalar(
            select(User).where(User.id == __import__("uuid").UUID(user_id.decode()))
        )
        if user_id
        else None
    )
    if not user or not user.is_active:
        raise HTTPException(401, "Session expired")
    return user


def same_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Cross-origin request denied")


@router.post("/login")
def login(
    body: Credentials,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    same_origin(request)
    client = cache()
    try:
        # Global limit is intentional for a single-user local system; do not trust proxy headers.
        attempts = client.incr("login-attempts")
        if attempts == 1:
            client.expire("login-attempts", 60)
        if attempts > 10:
            raise HTTPException(429, "Too many login attempts")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Session service unavailable") from None
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    try:
        password_hasher.verify(
            user.password_hash if user else DUMMY_HASH, body.password
        )
        valid = bool(user and user.is_active)
    except VerificationError:
        valid = False
    db.add(
        AuditLog(
            event_type="login_success" if valid else "login_failure",
            actor_id=user.id if user else None,
        )
    )
    db.commit()
    if not valid:
        raise HTTPException(401, "Invalid credentials")
    token = secrets.token_urlsafe(32)
    settings = get_settings()
    client.setex(
        "session:" + hashlib.sha256(token.encode()).hexdigest(),
        settings.session_ttl_seconds,
        str(user.id),
    )
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="strict",
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    return {"email": user.email}


@router.get("/me")
def me(user: User = Depends(require_user)):
    return {"email": user.email}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    same_origin(request)
    token = request.cookies.get("session", "")
    cache().delete("session:" + hashlib.sha256(token.encode()).hexdigest())
    response.delete_cookie("session", path="/")
    db.add(AuditLog(event_type="logout", actor_id=user.id))
    db.commit()
    return {"status": "ok"}
