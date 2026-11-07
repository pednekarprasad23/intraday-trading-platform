"""Authenticated, bounded catalog-only historical status (no filesystem paths)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import HistoricalGap, HistoricalImportJob, HistoricalPartition

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
            )
            for row in rows
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
