"""Authenticated, bounded historical status and verified candle reads."""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.config import get_settings
from app.database import get_db
from app.historical.reader import read_sessions
from app.models import HistoricalGap, HistoricalImportJob, HistoricalPartition, Instrument

router = APIRouter(prefix="/api/v1/historical", dependencies=[Depends(require_user)])


@router.get("/imports")
def imports(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(HistoricalImportJob))
    rows = db.scalars(
        select(HistoricalImportJob)
        .order_by(HistoricalImportJob.created_at.desc(), HistoricalImportJob.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "total": total,
        "items": [
            dict(
                id=row.id,
                provider=row.provider,
                instrument_id=row.instrument_id,
                timeframe=row.timeframe,
                session_date=row.session_date,
                source_sha256=row.source_sha256,
                provider_response_sha256=row.provider_response_sha256,
                provider_retrieved_at=row.provider_retrieved_at,
                status=row.status,
                row_count=row.row_count,
                duplicate_count=row.duplicate_count,
                reject_count=row.reject_count,
                gap_count=row.gap_count,
                conflict_count=row.conflict_count,
                error_summary=row.error_summary,
                requested_from=row.requested_from,
                requested_to=row.requested_to,
                observed_from=row.observed_from,
                observed_to=row.observed_to,
                created_at=row.created_at,
            )
            for row in rows
        ],
    }


@router.get("/partitions")
def partitions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List historical partitions with instrument metadata.

    P1-B: Returns instrument metadata from denormalized fields in HistoricalPartition
    table for efficient querying. Fields are populated when partitions are created.
    """
    total = db.scalar(select(func.count()).select_from(HistoricalPartition))
    rows = db.scalars(
        select(HistoricalPartition)
        .order_by(HistoricalPartition.session_date.desc(), HistoricalPartition.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "total": total,
        "items": [
            dict(
                id=row.id,
                provider=row.provider,
                instrument_id=row.instrument_id,
                timeframe=row.timeframe,
                session_date=row.session_date,
                checksum_sha256=row.checksum_sha256,
                row_count=row.row_count,
                # P1-B: Include instrument metadata (denormalized for performance)
                instrument_canonical_symbol=row.instrument_canonical_symbol,
                instrument_display_name=row.instrument_display_name,
                underlying_canonical_symbol=row.underlying_canonical_symbol,
                option_type=row.option_type,
                strike_price=row.strike_price,
            )
            for row in rows
        ],
    }


@router.get("/partitions/{partition_id}/candles")
def partition_candles(
    partition_id: UUID,
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Read verified candle data for a partition.

    P1-B: Includes instrument metadata in response for client-side display.
    Metadata is denormalized in HistoricalPartition table for efficient access.
    """
    partition = db.get(HistoricalPartition, partition_id)
    if partition is None:
        raise HTTPException(status_code=404, detail="Partition not found")
    try:
        session = read_sessions(
            db,
            Path(get_settings().historical_data_root),
            provider=partition.provider,
            instrument_id=partition.instrument_id,
            timeframe=partition.timeframe,
            dates=(partition.session_date,),
        )[0]
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    bars = session.bars[offset : offset + limit]
    return {
        "partition_id": str(partition.id),
        "provider": partition.provider,
        "instrument_id": str(partition.instrument_id),
        "timeframe": partition.timeframe,
        "session_date": partition.session_date,
        "checksum_sha256": partition.checksum_sha256,
        # P1-B: Include instrument metadata in candle response
        "instrument_canonical_symbol": partition.instrument_canonical_symbol,
        "instrument_display_name": partition.instrument_display_name,
        "underlying_canonical_symbol": partition.underlying_canonical_symbol,
        "option_type": partition.option_type,
        "strike_price": partition.strike_price,
        "total": len(session.bars),
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "bar_time": bar.bar_time,
                "open": str(bar.open),
                "high": str(bar.high),
                "low": str(bar.low),
                "close": str(bar.close),
                "volume": str(bar.volume),
            }
            for bar in bars
        ],
    }


@router.get("/imports/{job_id}/gaps")
def gaps(
    job_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    job = db.get(HistoricalImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import not found")
    rows = db.scalars(
        select(HistoricalGap)
        .where(HistoricalGap.job_id == job_id)
        .order_by(HistoricalGap.bar_time)
        .limit(limit)
        .offset(offset)
    ).all()
    return {"total": job.gap_count, "items": [row.bar_time for row in rows]}
