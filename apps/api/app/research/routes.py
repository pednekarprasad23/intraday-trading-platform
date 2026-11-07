"""Authenticated read-only ranking endpoints.

Computes rankings on-the-fly from existing BacktestReport and
WalkForwardReport metrics JSON.  No new database model.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import get_db
from app.models import BacktestReport, Instrument, WalkForwardReport
from app.research.commentary import generate as commentary_generate
from app.research.scoring import rank_candidates

router = APIRouter(
    prefix="/api/v1/research",
    dependencies=[Depends(require_user)],
)


def _build_candidate(report):
    """Build a ranking candidate dict from a BacktestReport or WalkForwardReport."""
    metrics = report.metrics or {}
    sources = report.sources or []
    session_count = len(sources) if sources else 0

    evidence = {
        "metrics": metrics,
        "sources": sources,
        "warnings": report.warnings or [],
    }

    return {
        "metrics": metrics,
        "session_count": session_count,
        "structure_level_count": 0,
        "instrument_id": report.instrument_id,
        "strategy_id": report.strategy_id,
        "strategy_version": report.strategy_version,
        "session_date": sources[0].get("session_date", "unknown") if sources else "unknown",
        "evidence": evidence,
    }


def _ranking_to_dict(ranking) -> dict:
    """Convert a Ranking dataclass to a JSON-serializable dict."""
    return {
        "candidate_id": ranking.candidate_id,
        "strategy_id": ranking.strategy_id,
        "strategy_version": ranking.strategy_version,
        "instrument_id": str(ranking.instrument_id),
        "session_date": ranking.session_date,
        "composite_score": float(ranking.composite_score),
        "score_breakdown": ranking.score_breakdown,
        "sub_scores": ranking.sub_scores,
        "is_rejected": ranking.is_rejected,
        "rejection_reasons": list(ranking.rejection_reasons),
        "ranking_version": ranking.ranking_version,
        "commentary": commentary_generate(ranking),
        "evidence": ranking.evidence,
    }


@router.get("/rankings")
def rankings(
    strategy_id: str | None = Query(None, description="Filter by strategy ID"),
    rejected_only: bool = Query(False, description="Show only rejected candidates"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated ranked list of all candidates."""
    # Fetch all backtest reports
    bt_rows = db.scalars(select(BacktestReport)).all()
    # Fetch all walk-forward reports
    wf_rows = db.scalars(select(WalkForwardReport)).all()

    candidates = [_build_candidate(r) for r in bt_rows] + [_build_candidate(r) for r in wf_rows]

    if strategy_id:
        candidates = [c for c in candidates if c["strategy_id"] == strategy_id]

    rankings_list = rank_candidates(candidates)

    if rejected_only:
        rankings_list = [r for r in rankings_list if r.is_rejected]

    total = len(rankings_list)
    page = rankings_list[offset: offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_ranking_to_dict(r) for r in page],
    }


@router.get("/rankings/latest")
def latest_rankings(
    strategy_id: str | None = Query(None, description="Filter by strategy ID"),
    db: Session = Depends(get_db),
):
    """Latest (highest-scoring) ranking per unique candidate."""
    bt_rows = db.scalars(select(BacktestReport)).all()
    wf_rows = db.scalars(select(WalkForwardReport)).all()

    candidates = [_build_candidate(r) for r in bt_rows] + [_build_candidate(r) for r in wf_rows]
    rankings_list = rank_candidates(candidates)

    # Deduplicate by candidate_id, keeping the first (highest score)
    seen: set[str] = set()
    unique: list = []
    for r in rankings_list:
        if r.candidate_id not in seen:
            seen.add(r.candidate_id)
            unique.append(r)

    if strategy_id:
        unique = [r for r in unique if r.strategy_id == strategy_id]

    return {
        "total": len(unique),
        "items": [_ranking_to_dict(r) for r in unique],
    }
