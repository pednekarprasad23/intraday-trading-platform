import logging
from uuid import uuid4

import redis
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.historical.routes import router as historical_router
from app.backtesting.routes import router as research_router
from app.database import engine, get_db
from app.models import Instrument, ProviderSymbol
from app.market_data.mt5 import router as mt5_router
from app.market_data.angelone import router as angelone_router
from app.market_data.coverage import router as coverage_router
from app.auth import router as auth_router, require_user
from app.research.routes import router as research_ranking_router
from app.providers.dhan import router as dhan_router
from app.market_data.dhan import router as dhan_live_router
from app.paper_trading.routes import router as paper_router
from app.paper_trading.demo import router as demo_router
from app.monitoring.routes import router as monitoring_router
from sqlalchemy import func

settings = get_settings()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("intraday.api")
app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(auth_router)
app.include_router(mt5_router)
app.include_router(angelone_router)
app.include_router(coverage_router)
app.include_router(historical_router)
app.include_router(research_router)
app.include_router(research_ranking_router)
app.include_router(dhan_router)  # Phase 3: Dhan provider metadata
app.include_router(dhan_live_router)  # Dhan live data & signals
app.include_router(paper_router)  # Phase 4: Paper trading
app.include_router(demo_router)  # Phase 5: Demo order testing
app.include_router(monitoring_router)  # Phase 7: Monitoring endpoints


@app.middleware("http")
async def correlation_id(request: Request, call_next):
    request_id = str(uuid4())
    response: Response = await call_next(request)
    logger.info(
        __import__("json").dumps(
            {
                "event": "request",
                "request_id": request_id,
                "method": request.method,
                "status": response.status_code,
            }
        )
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def dependency_health() -> dict[str, str]:
    health = {"database": "ok", "redis": "ok"}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        health["database"] = "unavailable"
    try:
        redis.Redis.from_url(
            settings.redis_url, socket_connect_timeout=0.5, socket_timeout=0.5
        ).ping()
    except Exception:
        health["redis"] = "unavailable"
    return health


@app.get("/api/v1/health/live")
def live():
    return {"status": "ok"}


@app.get("/api/v1/health/ready")
def ready():
    dependencies = dependency_health()
    if any(value != "ok" for value in dependencies.values()):
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "dependencies": dependencies},
        )
    return {"status": "ready", "dependencies": dependencies}


@app.get("/api/v1/system/status", dependencies=[Depends(require_user)])
def system_status():
    # Check actual credential presence without exposing secrets
    credential_exists = False
    try:
        import os
        key_path = settings.credential_key_path
        credential_exists = os.path.exists(key_path) and os.path.getsize(key_path) > 0
    except Exception:
        pass

    return {
        "version": settings.app_version,
        "environment": settings.app_env,
        "trading_mode": "PAPER_TRADING",
        "live_trading_enabled": False,
        "market_data": "credential_present" if credential_exists else "no_credential",
        "market_provider": "DHAN",
        "market_data_provenance": "dhan_api_v2",
        "demo_data": False,
        "dependencies": dependency_health(),
    }


@app.get("/api/v1/instruments", dependencies=[Depends(require_user)])
def instruments(
    search: str | None = None,
    asset_class: str | None = None,
    exchange: str | None = None,
    active: bool | None = True,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    if limit < 1 or limit > 250 or offset < 0:
        raise HTTPException(
            status_code=422, detail="limit must be 1..250 and offset non-negative"
        )
    query = select(Instrument)
    if search:
        query = query.where(
            Instrument.canonical_symbol.ilike(f"%{search}%")
            | Instrument.display_name.ilike(f"%{search}%")
        )
    if asset_class:
        query = query.where(Instrument.asset_class == asset_class.upper())
    if exchange:
        query = query.where(Instrument.exchange == exchange.upper())
    if active is not None:
        query = query.where(Instrument.is_active == active)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Instrument.canonical_symbol).limit(limit).offset(offset)
    ).all()
    items = [
        {
            "id": str(row.id),
            "canonical_symbol": row.canonical_symbol,
            "display_name": row.display_name,
            "asset_class": row.asset_class,
            "exchange": row.exchange,
            "is_active": row.is_active,
            "data_available": row.data_available,
            "execution_enabled": row.execution_enabled,
            "demo": row.is_demo,
        }
        for row in rows
    ]
    mappings = db.scalars(
        select(ProviderSymbol).where(
            ProviderSymbol.instrument_id.in_([row.id for row in rows])
        )
    ).all()
    for item in items:
        item["provider_mappings"] = [
            {
                "provider": m.provider,
                "provider_instrument_key": m.provider_instrument_key,
                "data_enabled": m.data_enabled,
                "provider_exchange": m.provider_exchange,
                "last_verified_at": m.last_verified_at.isoformat()
                if m.last_verified_at
                else None,
                "execution_enabled": m.execution_enabled,
            }
            for m in mappings
            if str(m.instrument_id) == item["id"]
        ]
    return {"items": items, "total": total}


# Public endpoints for frontend - no auth required
@app.get("/api/v1/public/instruments", response_model=dict)
def public_instruments(
    search: str | None = None,
    asset_class: str | None = None,
    exchange: str | None = None,
    active: bool = True,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Public instruments list - no auth required for frontend."""
    if limit < 1 or limit > 250 or offset < 0:
        raise HTTPException(
            status_code=422, detail="limit must be 1..250 and offset non-negative"
        )
    query = select(Instrument)
    if search:
        query = query.where(
            Instrument.canonical_symbol.ilike(f"%{search}%")
            | Instrument.display_name.ilike(f"%{search}%")
        )
    if asset_class:
        query = query.where(Instrument.asset_class == asset_class.upper())
    if exchange:
        query = query.where(Instrument.exchange == exchange.upper())
    if active is not None:
        query = query.where(Instrument.is_active == active)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Instrument.canonical_symbol).limit(limit).offset(offset)
    ).all()
    items = [
        {
            "id": str(row.id),
            "canonical_symbol": row.canonical_symbol,
            "display_name": row.display_name,
            "asset_class": row.asset_class,
            "exchange": row.exchange,
            "is_active": row.is_active,
            "data_available": row.data_available,
            "execution_enabled": row.execution_enabled,
            "demo": row.is_demo,
        }
        for row in rows
    ]
    mappings = db.scalars(
        select(ProviderSymbol).where(
            ProviderSymbol.instrument_id.in_([row.id for row in rows])
        )
    ).all()
    for item in items:
        item["provider_mappings"] = [
            {
                "provider": m.provider,
                "provider_instrument_key": m.provider_instrument_key,
                "data_enabled": m.data_enabled,
                "provider_exchange": m.provider_exchange,
                "last_verified_at": m.last_verified_at.isoformat()
                if m.last_verified_at
                else None,
                "execution_enabled": m.execution_enabled,
            }
            for m in mappings
            if str(m.instrument_id) == item["id"]
        ]
    return {"items": items, "total": total}
