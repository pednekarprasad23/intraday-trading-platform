"""Project lifecycle state machine and transition service."""

import json
from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.projects.models import Project, ProjectStatus, ProjectStrategyAssignment


VALID_TRANSITIONS: dict[ProjectStatus, set[ProjectStatus]] = {
    ProjectStatus.CREATED: {ProjectStatus.STOPPED, ProjectStatus.ARCHIVED},
    ProjectStatus.STOPPED: {ProjectStatus.STARTING, ProjectStatus.ARCHIVED},
    ProjectStatus.STARTING: {ProjectStatus.RUNNING, ProjectStatus.ERROR},
    ProjectStatus.RUNNING: {ProjectStatus.PAUSED, ProjectStatus.STOPPING, ProjectStatus.ERROR},
    ProjectStatus.PAUSED: {ProjectStatus.RUNNING, ProjectStatus.STOPPING, ProjectStatus.ERROR},
    ProjectStatus.STOPPING: {ProjectStatus.STOPPED, ProjectStatus.ERROR},
    ProjectStatus.ERROR: {ProjectStatus.STOPPED, ProjectStatus.ARCHIVED},
    ProjectStatus.ARCHIVED: set(),
}


def transition_project(
    db: Session,
    project_id: UUID,
    target_status: ProjectStatus,
    actor_id: UUID | None = None,
    actor_email: str = "system",
) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    current_status = project.status
    if target_status not in VALID_TRANSITIONS.get(current_status, set()):
        raise HTTPException(
            400,
            f"Invalid project state transition from {current_status} to {target_status}",
        )

    old_status = project.status
    project.status = target_status
    project.updated_at = datetime.now(timezone.utc)

    audit = AuditLog(
        actor_id=actor_id,
        event_type="PROJECT_STATUS_TRANSITION",
        details=json.dumps({
            "project_id": str(project.id),
            "old_status": old_status.value,
            "new_status": target_status.value,
            "actor_email": actor_email,
        }),
    )
    db.add(audit)
    db.commit()
    db.refresh(project)
    return project


def create_project(
    db: Session,
    name: str,
    slug: str,
    description: str | None = None,
    config: dict | None = None,
    actor_id: UUID | None = None,
    actor_email: str = "system",
) -> Project:
    existing = db.query(Project).filter((Project.name == name) | (Project.slug == slug)).first()
    if existing:
        raise HTTPException(400, "Project with name or slug already exists")

    project = Project(
        name=name,
        slug=slug,
        description=description,
        status=ProjectStatus.CREATED,
        config=config or {},
    )
    db.add(project)
    db.flush()

    audit = AuditLog(
        actor_id=actor_id,
        event_type="PROJECT_CREATED",
        details=json.dumps({
            "project_id": str(project.id),
            "name": name,
            "slug": slug,
            "actor_email": actor_email,
        }),
    )
    db.add(audit)
    db.commit()
    db.refresh(project)
    return project


def assign_strategy(
    db: Session,
    project_id: UUID,
    strategy_id: str,
    role: str = "primary",
    priority: int = 1,
    actor_id: UUID | None = None,
    actor_email: str = "system",
) -> ProjectStrategyAssignment:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    existing = db.query(ProjectStrategyAssignment).filter_by(
        project_id=project_id, strategy_id=strategy_id
    ).first()
    if existing:
        existing.role = role
        existing.priority = priority
        assignment = existing
    else:
        assignment = ProjectStrategyAssignment(
            project_id=project_id,
            strategy_id=strategy_id,
            role=role,
            priority=priority,
        )
        db.add(assignment)

    audit = AuditLog(
        actor_id=actor_id,
        event_type="PROJECT_STRATEGY_ASSIGNED",
        details=json.dumps({
            "project_id": str(project.id),
            "strategy_id": strategy_id,
            "role": role,
            "actor_email": actor_email,
        }),
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)
    return assignment
