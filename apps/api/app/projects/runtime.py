"""Project runtime activation, heartbeat reconciliation, and sandbox execution service (V2.6 Phase 3)."""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, StrategyVersion
from app.projects.models import Project, ProjectStatus, ProjectRun, RunStatus
from app.projects.sandbox import validate_and_snapshot_parameters
from app.paper_trading.models import KillSwitch, KillSwitchState


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
    project = db.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
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


def start_runtime(
    db: Session,
    project_id: UUID,
    actor_id: UUID | None = None,
    actor_email: str = "system",
) -> Project:
    """Activate real project runtime.

    Sequence:
    1. Row lock project.
    2. Transition CREATED -> STOPPED -> STARTING if needed.
    3. Initialize runtime instance ID and heartbeat timestamp.
    4. Transition STARTING -> RUNNING upon successful activation.
    If activation fails, transition to ERROR.
    """
    project = db.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if not project:
        raise HTTPException(404, "Project not found")

    if project.status == ProjectStatus.CREATED:
        transition_project(db, project_id, ProjectStatus.STOPPED, actor_id, actor_email)

    if project.status == ProjectStatus.STOPPED:
        transition_project(db, project_id, ProjectStatus.STARTING, actor_id, actor_email)

    if project.status != ProjectStatus.STARTING:
        raise HTTPException(400, f"Cannot start project from status {project.status}")

    try:
        instance_id = f"rt-{uuid4()}"
        now = datetime.now(timezone.utc)
        project.runtime_instance_id = instance_id
        project.runtime_status = "RUNNING"
        project.heartbeat_at = now
        project.last_error = None

        project = transition_project(db, project_id, ProjectStatus.RUNNING, actor_id, actor_email)

        audit = AuditLog(
            actor_id=actor_id,
            event_type="PROJECT_RUNTIME_STARTED",
            details=json.dumps({
                "project_id": str(project.id),
                "runtime_instance_id": instance_id,
                "actor_email": actor_email,
            }),
        )
        db.add(audit)
        db.commit()
        db.refresh(project)
        return project
    except Exception as e:
        project.runtime_status = "ERROR"
        project.last_error = str(e)
        db.commit()
        raise HTTPException(500, f"Runtime activation failed: {e}")


def stop_runtime(
    db: Session,
    project_id: UUID,
    actor_id: UUID | None = None,
    actor_email: str = "system",
) -> Project:
    """Stop project runtime and terminate active runs."""
    project = db.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if not project:
        raise HTTPException(404, "Project not found")

    if project.status in (ProjectStatus.RUNNING, ProjectStatus.PAUSED):
        transition_project(db, project_id, ProjectStatus.STOPPING, actor_id, actor_email)

    active_runs = db.scalars(
        select(ProjectRun)
        .where(ProjectRun.project_id == project_id)
        .where(ProjectRun.status.in_([RunStatus.QUEUED, RunStatus.STARTING, RunStatus.RUNNING]))
    ).all()

    now = datetime.now(timezone.utc)
    for run in active_runs:
        run.status = RunStatus.CANCELLED
        run.finished_at = now
        run.error_code = "RUNTIME_STOPPED"
        run.error_message = "Run cancelled due to project runtime stop."

    project.runtime_status = "STOPPED"
    project.runtime_instance_id = None
    project.heartbeat_at = None

    project = transition_project(db, project_id, ProjectStatus.STOPPED, actor_id, actor_email)

    audit = AuditLog(
        actor_id=actor_id,
        event_type="PROJECT_RUNTIME_STOPPED",
        details=json.dumps({
            "project_id": str(project.id),
            "actor_email": actor_email,
        }),
    )
    db.add(audit)
    db.commit()
    db.refresh(project)
    return project


def submit_run(
    db: Session,
    project_id: UUID,
    strategy_version_id: UUID,
    parameters: dict[str, Any] | None,
    requested_by: UUID | None = None,
    actor_email: str = "system",
) -> ProjectRun:
    """Submit a parameterized sandboxed strategy run for a project.

    Enforces:
    - One active run per project policy.
    - Global Kill Switch check (fail closed).
    - Immutable StrategyVersion association.
    - Parameter validation and canonical fingerprinting.
    """
    project = db.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if not project:
        raise HTTPException(404, "Project not found")

    if project.status != ProjectStatus.RUNNING or project.runtime_status != "RUNNING":
        raise HTTPException(400, "Project runtime is not RUNNING. Start project before submitting runs.")

    ks = db.scalar(select(KillSwitch).where(KillSwitch.name == "global"))
    if ks and ks.state == KillSwitchState.TRIGGERED:
        raise HTTPException(403, "Global Kill Switch is TRIGGERED. All execution paths are blocked.")

    active_run = db.scalar(
        select(ProjectRun)
        .where(ProjectRun.project_id == project_id)
        .where(ProjectRun.status.in_([RunStatus.QUEUED, RunStatus.STARTING, RunStatus.RUNNING]))
    )
    if active_run:
        raise HTTPException(400, "Project already has an active run. Only one active run per project is permitted.")

    sv = db.get(StrategyVersion, strategy_version_id)
    if not sv:
        raise HTTPException(404, "StrategyVersion not found")

    valid_params, param_fp = validate_and_snapshot_parameters(parameters)

    now = datetime.now(timezone.utc)
    run = ProjectRun(
        project_id=project_id,
        strategy_version_id=strategy_version_id,
        status=RunStatus.QUEUED,
        parameters_snapshot=valid_params,
        parameters_sha256=param_fp,
        requested_by=requested_by,
        runtime_instance_id=project.runtime_instance_id,
        started_at=now,
    )
    db.add(run)
    db.flush()

    run.status = RunStatus.RUNNING
    project.heartbeat_at = now

    audit = AuditLog(
        actor_id=requested_by,
        event_type="PROJECT_RUN_STARTED",
        details=json.dumps({
            "project_id": str(project.id),
            "run_id": str(run.id),
            "strategy_version_id": str(strategy_version_id),
            "parameters_sha256": param_fp,
            "actor_email": actor_email,
        }),
    )
    db.add(audit)
    db.commit()
    db.refresh(run)
    return run
