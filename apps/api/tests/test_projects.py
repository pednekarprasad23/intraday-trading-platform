"""Project control-plane unit and integration tests (V2.6 Phase 2)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.projects.models import Project, ProjectStatus, ExecutionMode, ProjectStrategyAssignment
from app.projects.service import create_project, transition_project, assign_strategy
from tests.test_historical import setup_db


def test_project_lifecycle_state_machine(tmp_path):
    """Verify project lifecycle transitions strictly follow valid state machine graph."""
    engine, _ = setup_db(tmp_path)
    with Session(engine) as db:
        project = create_project(
            db,
            name="Momentum Alpha",
            slug="momentum-alpha",
            description="Intraday EMA momentum strategy project",
            config={"timeframe": "1m", "risk_limit_inr": 50000},
        )

        assert project.status == ProjectStatus.CREATED
        assert project.execution_mode == ExecutionMode.PAPER

        # CREATED -> STOPPED
        project = transition_project(db, project.id, ProjectStatus.STOPPED)
        assert project.status == ProjectStatus.STOPPED

        # STOPPED -> STARTING -> RUNNING
        project = transition_project(db, project.id, ProjectStatus.STARTING)
        assert project.status == ProjectStatus.STARTING
        project = transition_project(db, project.id, ProjectStatus.RUNNING)
        assert project.status == ProjectStatus.RUNNING

        # RUNNING -> PAUSED -> RUNNING
        project = transition_project(db, project.id, ProjectStatus.PAUSED)
        assert project.status == ProjectStatus.PAUSED
        project = transition_project(db, project.id, ProjectStatus.RUNNING)
        assert project.status == ProjectStatus.RUNNING

        # RUNNING -> STOPPING -> STOPPED -> ARCHIVED
        project = transition_project(db, project.id, ProjectStatus.STOPPING)
        assert project.status == ProjectStatus.STOPPING
        project = transition_project(db, project.id, ProjectStatus.STOPPED)
        assert project.status == ProjectStatus.STOPPED
        project = transition_project(db, project.id, ProjectStatus.ARCHIVED)
        assert project.status == ProjectStatus.ARCHIVED


def test_invalid_project_transition(tmp_path):
    """Verify invalid state transitions raise HTTPException 400."""
    engine, _ = setup_db(tmp_path)
    with Session(engine) as db:
        project = create_project(
            db,
            name="Alpha V2",
            slug="alpha-v2",
        )
        # CREATED cannot jump directly to RUNNING without STOPPED / STARTING
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            transition_project(db, project.id, ProjectStatus.RUNNING)
        assert exc_info.value.status_code == 400


def test_strategy_assignment(tmp_path):
    """Verify strategy assignment and unique constraint per project+strategy."""
    engine, _ = setup_db(tmp_path)
    with Session(engine) as db:
        project = create_project(
            db,
            name="Options Alpha",
            slug="options-alpha",
        )

        assignment = assign_strategy(
            db,
            project_id=project.id,
            strategy_id="option-premium-ema-rsi",
            role="primary",
            priority=1,
        )
        assert assignment.strategy_id == "option-premium-ema-rsi"
        assert assignment.project_id == project.id

        # Re-assigning same strategy updates role/priority
        updated = assign_strategy(
            db,
            project_id=project.id,
            strategy_id="option-premium-ema-rsi",
            role="fallback",
            priority=2,
        )
        assert updated.role == "fallback"
        assert updated.priority == 2
        assert db.query(ProjectStrategyAssignment).filter_by(project_id=project.id).count() == 1
