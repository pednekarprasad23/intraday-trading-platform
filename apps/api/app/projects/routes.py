"""Project control-plane and runtime REST API endpoints (V2.6 Phase 3)."""

from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth import require_user
from app.database import get_db
from app.projects.models import ExecutionMode, Project, ProjectStatus, ProjectStrategyAssignment, ProjectRun, RunStatus
from app.projects.service import assign_strategy, create_project
from app.projects.runtime import start_runtime, stop_runtime, submit_run, transition_project

router = APIRouter(prefix="/api/v1/projects", dependencies=[Depends(require_user)], tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100)
    description: str | None = None
    config: dict[str, Any] | None = None


class StrategyAssignmentRequest(BaseModel):
    strategy_id: str = Field(..., max_length=100)
    role: str = Field(default="primary", max_length=50)
    priority: int = Field(default=1, ge=1)


class RunSubmitRequest(BaseModel):
    strategy_version_id: UUID
    parameters: dict[str, Any] | None = None


def _serialize_run(r: ProjectRun) -> dict:
    return {
        "id": r.id,
        "project_id": r.project_id,
        "strategy_version_id": r.strategy_version_id,
        "status": r.status.value,
        "parameters_snapshot": r.parameters_snapshot,
        "parameters_sha256": r.parameters_sha256,
        "requested_by": r.requested_by,
        "runtime_instance_id": r.runtime_instance_id,
        "error_code": r.error_code,
        "error_message": r.error_message,
        "result_summary": r.result_summary,
        "created_at": r.created_at,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
        "heartbeat_at": r.heartbeat_at,
    }


def _serialize_project(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "description": p.description,
        "status": p.status.value,
        "execution_mode": p.execution_mode.value,
        "config": p.config,
        "config_version": p.config_version,
        "runtime_status": p.runtime_status,
        "runtime_instance_id": p.runtime_instance_id,
        "heartbeat_at": p.heartbeat_at,
        "last_error": p.last_error,
        "strategies": [
            {
                "id": s.id,
                "strategy_id": s.strategy_id,
                "role": s.role,
                "priority": s.priority,
            }
            for s in (p.strategies or [])
        ],
        "runs": [_serialize_run(r) for r in (p.runs or [])],
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


@router.get("")
def list_projects(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List durable projects with strategies and recent runs."""
    rows = db.scalars(
        select(Project)
        .options(joinedload(Project.strategies), joinedload(Project.runs))
        .order_by(Project.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).unique().all()
    total = db.scalar(select(func.count()).select_from(Project))
    return {
        "total": total,
        "items": [_serialize_project(p) for p in rows],
    }


@router.post("", status_code=201)
def create_new_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Create a new project."""
    project = create_project(
        db,
        name=body.name,
        slug=body.slug,
        description=body.description,
        config=body.config,
        actor_id=getattr(user, "id", None),
        actor_email=getattr(user, "email", "system"),
    )
    return _serialize_project(project)


@router.get("/{project_id}")
def get_project(project_id: UUID, db: Session = Depends(get_db)):
    """Get project by ID with runtime health and runs."""
    project = db.scalars(
        select(Project)
        .options(joinedload(Project.strategies), joinedload(Project.runs))
        .where(Project.id == project_id)
    ).unique().first()
    if not project:
        raise HTTPException(404, "Project not found")
    return _serialize_project(project)


@router.post("/{project_id}/start")
def start_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Activate real project runtime."""
    proj = start_runtime(
        db, project_id, actor_id=getattr(user, "id", None), actor_email=getattr(user, "email", "system")
    )
    return _serialize_project(proj)


@router.post("/{project_id}/pause")
def pause_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Transition project status to PAUSED."""
    proj = transition_project(
        db, project_id, ProjectStatus.PAUSED, actor_id=getattr(user, "id", None), actor_email=getattr(user, "email", "system")
    )
    return _serialize_project(proj)


@router.post("/{project_id}/resume")
def resume_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Resume paused project to RUNNING."""
    proj = transition_project(
        db, project_id, ProjectStatus.RUNNING, actor_id=getattr(user, "id", None), actor_email=getattr(user, "email", "system")
    )
    return _serialize_project(proj)


@router.post("/{project_id}/stop")
def stop_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Stop project runtime and transition status to STOPPED."""
    proj = stop_runtime(
        db, project_id, actor_id=getattr(user, "id", None), actor_email=getattr(user, "email", "system")
    )
    return _serialize_project(proj)


@router.post("/{project_id}/archive")
def archive_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Archive project."""
    proj = transition_project(
        db, project_id, ProjectStatus.ARCHIVED, actor_id=getattr(user, "id", None), actor_email=getattr(user, "email", "system")
    )
    return _serialize_project(proj)


@router.post("/{project_id}/strategies")
def add_strategy_assignment(
    project_id: UUID,
    body: StrategyAssignmentRequest,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Assign a strategy to a project."""
    assignment = assign_strategy(
        db,
        project_id,
        strategy_id=body.strategy_id,
        role=body.role,
        priority=body.priority,
        actor_id=getattr(user, "id", None),
        actor_email=getattr(user, "email", "system"),
    )
    project = db.scalars(
        select(Project)
        .options(joinedload(Project.strategies), joinedload(Project.runs))
        .where(Project.id == project_id)
    ).unique().first()
    return _serialize_project(project)


@router.post("/{project_id}/runs", status_code=201)
def create_project_run(
    project_id: UUID,
    body: RunSubmitRequest,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Submit a parameterized sandboxed strategy run for a running project."""
    run = submit_run(
        db,
        project_id=project_id,
        strategy_version_id=body.strategy_version_id,
        parameters=body.parameters,
        requested_by=getattr(user, "id", None),
        actor_email=getattr(user, "email", "system"),
    )
    return _serialize_run(run)


@router.get("/{project_id}/runs")
def list_project_runs(
    project_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List runs for a project."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    query = select(ProjectRun).where(ProjectRun.project_id == project_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    runs = db.scalars(
        query.order_by(ProjectRun.created_at.desc()).limit(limit).offset(offset)
    ).all()

    return {
        "total": total,
        "items": [_serialize_run(r) for r in runs],
    }


@router.get("/{project_id}/runs/{run_id}")
def get_project_run(
    project_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
):
    """Get specific run detail."""
    run = db.get(ProjectRun, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(404, "Run not found")
    return _serialize_run(run)


@router.post("/{project_id}/runs/{run_id}/cancel")
def cancel_project_run(
    project_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Cancel an active run."""
    run = db.get(ProjectRun, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(404, "Run not found")

    if run.status in (RunStatus.QUEUED, RunStatus.STARTING, RunStatus.RUNNING):
        run.status = RunStatus.CANCELLED
        run.finished_at = datetime.now(timezone.utc)
        run.error_code = "USER_CANCELLED"
        run.error_message = "Run cancelled by operator request."
        db.commit()
        db.refresh(run)

    return _serialize_run(run)
