"""Discovery API read-only routes — V2.9B.

Exposes read-only market discovery universes and normalized option chain snapshots.
Strictly decoupled from execution, paper trading, and order routing.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.discovery.models import MarketUniverse
from app.discovery.provider import (
    FixtureDiscoveryAdapter,
    DiscoveryProviderError,
)

router = APIRouter(prefix="/api/v1/discovery", dependencies=[Depends(require_user)])


@router.get("/universes")
def list_universes(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """List registered discovery market universes."""
    universes = db.scalars(select(MarketUniverse).where(MarketUniverse.enabled == True)).all()
    if not universes:
        # Bootstrap default if empty
        from app.discovery.service import DiscoveryService
        DiscoveryService.bootstrap_nifty_options_universe(db)
        universes = db.scalars(select(MarketUniverse).where(MarketUniverse.enabled == True)).all()

    return [
        {
            "id": str(u.id),
            "name": u.name,
            "market": u.market,
            "exchange": u.exchange,
            "asset_class": u.asset_class,
            "instrument_type": u.instrument_type,
            "sector": u.sector,
            "underlying": u.underlying,
            "provider": u.provider,
            "enabled": u.enabled,
            "metadata": u.universe_metadata,
        }
        for u in universes
    ]


@router.get("/option-chain")
def get_option_chain_snapshot(
    underlying: str = Query(default="NIFTY", description="Underlying asset symbol"),
    expiry: str = Query(default="2026-11-26", description="Expiry date YYYY-MM-DD"),
) -> dict[str, Any]:
    """Get normalized option chain snapshot for underlying and expiry."""
    adapter = FixtureDiscoveryAdapter()
    try:
        snapshot = adapter.get_option_chain(underlying, expiry)
        return {
            "underlying": snapshot.underlying,
            "spot_price": str(snapshot.spot_price),
            "expiry": snapshot.expiry,
            "provider": snapshot.provider,
            "timestamp": snapshot.timestamp.isoformat(),
            "contract_count": len(snapshot.contracts),
            "contracts": [
                {
                    "market": c.market,
                    "exchange": c.exchange,
                    "underlying": c.underlying,
                    "instrument_type": c.instrument_type,
                    "expiry": c.expiry,
                    "strike": str(c.strike),
                    "option_type": c.option_type,
                    "canonical_contract_id": c.canonical_contract_id,
                    "provider": c.provider,
                    "provider_instrument_id": c.provider_instrument_id,
                    "last_price": str(c.last_price) if c.last_price else None,
                    "volume": c.volume,
                    "open_interest": c.open_interest,
                    "bid_price": str(c.bid_price) if c.bid_price else None,
                    "ask_price": str(c.ask_price) if c.ask_price else None,
                    "implied_volatility": str(c.implied_volatility) if c.implied_volatility else None,
                    "delta": str(c.delta) if c.delta else None,
                    "gamma": str(c.gamma) if c.gamma else None,
                    "theta": str(c.theta) if c.theta else None,
                    "vega": str(c.vega) if c.vega else None,
                    "lot_size": c.lot_size,
                    "tick_size": str(c.tick_size) if c.tick_size else None,
                    "snapshot_at": c.snapshot_at.isoformat(),
                }
                for c in snapshot.contracts
            ],
        }
    except DiscoveryProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
