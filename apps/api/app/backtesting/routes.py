"""Authenticated read-only research catalog; never an execution API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import (
    BacktestReport,
    HistoricalPartition,
    Instrument,
    ResearchEvaluation,
    StrategySignal,
    WalkForwardReport,
)

router = APIRouter(prefix="/api/v1/research", dependencies=[Depends(require_user)])


def _report(db, row):
    item = dict(
        id=row.id,
        fingerprint=row.fingerprint,
        input_fingerprint=row.input_fingerprint,
        provider=row.provider,
        demo=db.get(Instrument, row.instrument_id).is_demo,
        instrument_id=row.instrument_id,
        timeframe=row.timeframe,
        strategy_id=row.strategy_id,
        strategy_version=row.strategy_version,
        metrics=row.metrics,
        warnings=row.warnings,
        created_at=row.created_at,
        label="RESEARCH ONLY / SIMULATED / NO BROKER ORDER",
    )
    if isinstance(row, WalkForwardReport):
        item.update(
            kind="WALK_FORWARD",
            train_size=row.train_size,
            test_size=row.test_size,
            fold_count=len(row.folds),
        )
    else:
        item.update(kind="BACKTEST", trade_count=row.metrics.get("trade_count", 0))
    return item


def _page(db, model, limit, offset):
    rows = db.scalars(
        select(model)
        .order_by(model.created_at.desc(), model.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "total": db.scalar(select(func.count()).select_from(model)),
        "items": [_report(db, row) for row in rows],
    }


@router.get("/signals")
def signals(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(StrategySignal)
        .order_by(StrategySignal.decision_time.desc(), StrategySignal.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "total": db.scalar(select(func.count()).select_from(StrategySignal)),
        "items": [
            dict(
                id=row.id,
                instrument_id=row.instrument_id,
                strategy_version_id=row.strategy_version_id,
                decision_time=row.decision_time,
                direction=row.direction,
                input_sha256=row.input_sha256,
                provider=db.get(HistoricalPartition, row.partition_id).provider,
                demo=db.get(Instrument, row.instrument_id).is_demo,
                partition_sha256=db.get(
                    HistoricalPartition, row.partition_id
                ).checksum_sha256,
                partition_id=row.partition_id,
                quality="VALID",
                created_at=row.created_at,
                label="RESEARCH ONLY / NO BROKER ORDER",
            )
            for row in rows
        ],
    }


@router.get("/evaluations")
def evaluations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(ResearchEvaluation)
        .order_by(ResearchEvaluation.created_at.desc(), ResearchEvaluation.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "total": db.scalar(select(func.count()).select_from(ResearchEvaluation)),
        "items": [
            dict(
                id=row.id,
                instrument_id=row.instrument_id,
                decision_time=row.decision_time,
                direction=row.direction,
                quality=row.quality,
                reasons=row.reasons,
                strategy_id=row.strategy_id,
                strategy_version=row.strategy_version,
                strategy_config_sha256=row.strategy_config_sha256,
                input_sha256=row.input_sha256,
                provider=db.get(HistoricalPartition, row.partition_id).provider,
                demo=db.get(Instrument, row.instrument_id).is_demo,
                partition_id=row.partition_id,
                partition_sha256=db.get(
                    HistoricalPartition, row.partition_id
                ).checksum_sha256,
                created_at=row.created_at,
                label="RESEARCH ONLY / NO BROKER ORDER",
            )
            for row in rows
        ],
    }


@router.get("/backtests")
def backtests(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return _page(db, BacktestReport, limit, offset)


@router.get("/walk-forwards")
def walk_forwards(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return _page(db, WalkForwardReport, limit, offset)


@router.get("/backtests/{report_id}")
def backtest(report_id: UUID, db: Session = Depends(get_db)):
    row = db.get(BacktestReport, report_id)
    if row is None:
        raise HTTPException(404, "Report not found")
    return {
        **_report(db, row),
        "simulation_config": row.simulation_config,
        "strategy_config": row.strategy_config,
        "sources": row.sources,
        "trade_summary": row.trade_summary,
        "event_summary": row.event_summary,
    }


@router.get("/walk-forwards/{report_id}")
def walk_forward_report(report_id: UUID, db: Session = Depends(get_db)):
    row = db.get(WalkForwardReport, report_id)
    if row is None:
        raise HTTPException(404, "Report not found")
    return {
        **_report(db, row),
        "simulation_config": row.simulation_config,
        "strategy_config": row.strategy_config,
        "sources": row.sources,
        "folds": row.folds,
    }
