"""Authenticated read-only view of verified mappings and historical coverage."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import HistoricalPartition, Instrument, ProviderSymbol

router = APIRouter(prefix="/api/v1/market", dependencies=[Depends(require_user)])


@router.get("/coverage")
def market_data_coverage(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=100),
    provider: str | None = Query(None, max_length=50),
    asset_class: str | None = Query(None, max_length=30),
    exchange: str | None = Query(None, max_length=30),
    demo: bool | None = None,
    historical: bool | None = None,
    db: Session = Depends(get_db),
):
    """Report filtered stored coverage without implying a live market feed."""
    observed_at = datetime.now(timezone.utc)
    latest_session = (
        select(func.max(HistoricalPartition.session_date))
        .where(
            HistoricalPartition.instrument_id == ProviderSymbol.instrument_id,
            HistoricalPartition.provider == ProviderSymbol.provider,
        )
        .correlate(ProviderSymbol)
        .scalar_subquery()
    )
    partition_count = (
        select(func.count(HistoricalPartition.id))
        .where(
            HistoricalPartition.instrument_id == ProviderSymbol.instrument_id,
            HistoricalPartition.provider == ProviderSymbol.provider,
        )
        .correlate(ProviderSymbol)
        .scalar_subquery()
    )
    query = select(Instrument, ProviderSymbol).join(
        ProviderSymbol, ProviderSymbol.instrument_id == Instrument.id
    )
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Instrument.canonical_symbol.ilike(term),
                Instrument.display_name.ilike(term),
                ProviderSymbol.provider_instrument_key.ilike(term),
            )
        )
    if provider:
        query = query.where(ProviderSymbol.provider == provider.upper())
    if asset_class:
        query = query.where(Instrument.asset_class == asset_class.upper())
    if exchange:
        query = query.where(Instrument.exchange == exchange.upper())
    if demo is not None:
        query = query.where(Instrument.is_demo == demo)
    if historical is not None:
        query = query.where(
            (partition_count > 0) if historical else (partition_count == 0)
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.add_columns(
            latest_session.label("latest_historical_session"),
            partition_count.label("historical_partition_count"),
        )
        .order_by(
            Instrument.canonical_symbol,
            ProviderSymbol.provider,
            ProviderSymbol.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "live_feed_status": "unavailable",
        "observed_at": observed_at,
        "live_feed_note": "A provider mapping or historical partition does not establish a live feed or current quote entitlement.",
        "items": [
            {
                "instrument_id": str(instrument.id),
                "canonical_symbol": instrument.canonical_symbol,
                "display_name": instrument.display_name,
                "asset_class": instrument.asset_class,
                "exchange": instrument.exchange,
                "demo": instrument.is_demo,
                "provider": mapping.provider,
                "provider_instrument_key": mapping.provider_instrument_key,
                "provider_exchange": mapping.provider_exchange,
                "mapping_verified_at": mapping.last_verified_at,
                "data_enabled": mapping.data_enabled,
                "execution_enabled": mapping.execution_enabled,
                "latest_historical_session": latest_session_value,
                "historical_partition_count": partition_count_value,
                "live_quote_available": False,
            }
            for instrument, mapping, latest_session_value, partition_count_value in rows
        ],
        "total": total,
    }
