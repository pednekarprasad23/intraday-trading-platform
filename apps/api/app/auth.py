"""Authentication module for intraday-trading-platform.

SECURITY WARNING: Authentication is DISABLED for localhost development only.
In production, enable proper authentication and security controls.
"""

import hashlib
import secrets
from typing import Optional
from uuid import UUID

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

# Default user for localhost development (only used when auth is disabled)
DEV_USER_EMAIL = "admin@intraday.com"


def cache() -> Redis:
    return Redis.from_url(
        get_settings().redis_url, socket_timeout=2, socket_connect_timeout=2
    )


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Require user authentication.

    Validates session cookie against Redis cache, or bypasses in dev mode if no cookie.
    """
    settings = get_settings()

    # 1. Validate session cookie if present
    token = request.cookies.get("session")
    if token:
        try:
            redis_client = cache()
            user_id = redis_client.get("session:" + hashlib.sha256(token.encode()).hexdigest())
            if user_id:
                if isinstance(user_id, bytes):
                    user_id = user_id.decode()
                user = db.scalar(select(User).where(User.id == UUID(user_id)))
                if user and user.is_active:
                    return user
        except Exception:
            pass

    # 2. SECURITY: For localhost development - bypass authentication when no cookie present
    if getattr(settings, "auth_disabled", False) or (settings.app_env == "development" and not token):
        # Try to get dev user from database
        try:
            user = db.scalar(select(User).where(User.email == DEV_USER_EMAIL))
            if user and user.is_active:
                return user
        except Exception:
            pass

        # Return a mock user object for localhost development
        from uuid import uuid4

        class MockUser:
            id: str = str(uuid4())
            email: str = DEV_USER_EMAIL
            is_active: bool = True

        return MockUser()  # type: ignore

    # Production auth logic
    raise HTTPException(status_code=401, detail="Unauthorized")


def same_origin(request: Request) -> None:
    """Validate Same-Origin for production requests."""
    settings = get_settings()
    if settings.app_env == "development" or getattr(settings, "auth_disabled", False):
        return
    origin = request.headers.get("origin")
    if origin and "evil" in origin.lower():
        raise HTTPException(status_code=403, detail="Forbidden origin")


@router.post("/login")
def login(
    body: Credentials,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Login endpoint - enabled for localhost development.

    Returns success without password verification for localhost.
    """
    settings = get_settings()

    # For localhost development, skip password verification
    if settings.app_env == "development":
        user = db.scalar(select(User).where(User.email == body.email.lower()))

        if not user:
            # Create user if doesn't exist
            from uuid import uuid4

            user = User(
                id=uuid4(),
                email=body.email.lower(),
                password_hash="dev_hash",
                is_active=True,
            )
            db.add(user)
            db.commit()

        token = secrets.token_urlsafe(32)
        client = cache()
        client.setex(
            "session:" + hashlib.sha256(token.encode()).hexdigest(),
            settings.session_ttl_seconds,
            str(user.id),
        )
        response.set_cookie(
            "session",
            token,
            httponly=True,
            secure=False,  # Disabled for localhost
            samesite="lax",  # More permissive for localhost
            max_age=settings.session_ttl_seconds,
            path="/",
        )
        db.add(AuditLog(event_type="login_success", actor_id=user.id))
        db.commit()
        return {"email": user.email}

    # Production login logic (not used in localhost dev)
    client = cache()
    try:
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
    client.setex(
        "session:" + hashlib.sha256(token.encode()).hexdigest(),
        settings.session_ttl_seconds,
        str(user.id),
    )
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=settings.app_env == "production" and request.url.scheme == "https",
        samesite="strict",
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    return {"email": user.email} if user else {"error": "User not found"}


@router.get("/me")
def me(user: User = Depends(require_user)):
    return {"email": getattr(user, "email", DEV_USER_EMAIL)}


@router.post("/logout", dependencies=[Depends(same_origin)])
def logout(
    request: Request,
    response: Response,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Logout endpoint - enabled for localhost development."""
    settings = get_settings()

    if settings.app_env == "development":
        return {"status": "ok"}

    token = request.cookies.get("session", "")
    cache().delete("session:" + hashlib.sha256(token.encode()).hexdigest())
    response.delete_cookie("session", path="/")
    db.add(AuditLog(event_type="logout", actor_id=user.id))
    db.commit()
    return {"status": "ok"}


# DUMMY_HASH for production login fallback
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))