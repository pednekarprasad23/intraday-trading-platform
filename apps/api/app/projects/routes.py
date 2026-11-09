"""Project control-plane REST API endpoints."""

from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth import require_user
from app.database import get_db
from app.projects.models import ExecutionMode, Project, ProjectStatus, ProjectStrategyAssignment
from app.projects.service import assign_strategy, create_project, transition_project

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
        "strategies": [
            {
                "id": s.id,
                "strategy_id": s.strategy_id,
                "role": s.role,
                "priority": s.priority,
            }
            for s in (p.strategies or [])
        ],
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


@router.get("")
def list_projects(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List durable projects."""
    rows = db.scalars(
        select(Project)
        .options(joinedload(Project.strategies))
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
    """Get project by ID."""
    project = db.scalars(
        select(Project)
        .options(joinedload(Project.strategies))
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
    """Transition project status to STARTING then RUNNING."""
    proj = db.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    if proj.status == ProjectStatus.STOPPED:
        transition_project(db, project_id, ProjectStatus.STARTING, actor_email=getattr(user, "email", "system"))
    proj = transition_project(db, project_id, ProjectStatus.RUNNING, actor_email=getattr(user, "email", "system"))
    return _serialize_project(proj)


@router.post("/{project_id}/pause")
def pause_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Transition project status to PAUSED."""
    proj = transition_project(
        db, project_id, ProjectStatus.PAUSED, actor_email=getattr(user, "email", "system")
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
        db, project_id, ProjectStatus.RUNNING, actor_email=getattr(user, "email", "system")
    )
    return _serialize_project(proj)


@router.post("/{project_id}/stop")
def stop_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Transition project status to STOPPING then STOPPED."""
    proj = db.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    if proj.status in (ProjectStatus.RUNNING, ProjectStatus.PAUSED):
        transition_project(db, project_id, ProjectStatus.STOPPING, actor_email=getattr(user, "email", "system"))
    proj = transition_project(db, project_id, ProjectStatus.STOPPED, actor_email=getattr(user, "email", "system"))
    return _serialize_project(proj)


@router.post("/{project_id}/archive")
def archive_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(require_user),
):
    """Archive project."""
    proj = transition_project(
        db, project_id, ProjectStatus.ARCHIVED, actor_email=getattr(user, "email", "system")
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
        actor_email=getattr(user, "email", "system"),
    )
    project = db.get(Project, project_id)
    return _serialize_project(project)
