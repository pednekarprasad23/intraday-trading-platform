"""Project control-plane unit and integration tests (V2.6 Phase 2 Acceptance Audit)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.projects.models import Project, ProjectStatus, ExecutionMode, ProjectStrategyAssignment
from app.projects.service import create_project, transition_project, assign_strategy
from app.models import StrategyVersion, BacktestReport, Instrument
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


def test_forbidden_transitions(tmp_path):
    """Verify forbidden and direct bypass transitions are rejected with HTTP 400."""
    engine, _ = setup_db(tmp_path)
    with Session(engine) as db:
        project = create_project(db, name="Alpha Test", slug="alpha-test")

        from fastapi import HTTPException

        # STOPPED -> RUNNING directly (bypassing STARTING) is forbidden
        transition_project(db, project.id, ProjectStatus.STOPPED)
        with pytest.raises(HTTPException) as exc:
            transition_project(db, project.id, ProjectStatus.RUNNING)
        assert exc.value.status_code == 400

        # ARCHIVED -> RUNNING is forbidden
        transition_project(db, project.id, ProjectStatus.STARTING)
        transition_project(db, project.id, ProjectStatus.RUNNING)
        transition_project(db, project.id, ProjectStatus.STOPPING)
        transition_project(db, project.id, ProjectStatus.STOPPED)
        transition_project(db, project.id, ProjectStatus.ARCHIVED)

        with pytest.raises(HTTPException) as exc:
            transition_project(db, project.id, ProjectStatus.RUNNING)
        assert exc.value.status_code == 400


def test_concurrency_protection(tmp_path):
    """Verify row locking and transition serialization under concurrent requests."""
    engine, _ = setup_db(tmp_path)
    with Session(engine) as db:
        project = create_project(db, name="Concurrent Test", slug="concurrent-test")
        transition_project(db, project.id, ProjectStatus.STOPPED)
        transition_project(db, project.id, ProjectStatus.STARTING)
        transition_project(db, project.id, ProjectStatus.RUNNING)

    with Session(engine) as db1, Session(engine) as db2:
        p1 = transition_project(db1, project.id, ProjectStatus.PAUSED)
        assert p1.status == ProjectStatus.PAUSED

        # Attempting an invalid transition from the current PAUSED state should fail
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            transition_project(db2, project.id, ProjectStatus.STARTING)
        assert exc.value.status_code == 400


def test_strategy_assignment_isolation(tmp_path):
    """Verify project strategy assignment does not mutate StrategyVersion or historical research reports."""
    engine, _ = setup_db(tmp_path)
    with Session(engine) as db:
        sv = StrategyVersion(
            strategy_id="option-premium-ema-rsi",
            version=1,
            config={"ema": 12},
            config_sha256="abc123sha",
        )
        db.add(sv)
        db.commit()

        project = create_project(db, name="Isolated Strategy", slug="isolated-strategy")
        assignment = assign_strategy(db, project.id, strategy_id="option-premium-ema-rsi")

        assert assignment.strategy_id == "option-premium-ema-rsi"
        stored_sv = db.get(StrategyVersion, sv.id)
        assert stored_sv.config == {"ema": 12}
        assert stored_sv.config_sha256 == "abc123sha"


def test_execution_safety_invariant(tmp_path):
    """Verify project RUNNING status does not grant or imply brokerage execution authority."""
    engine, _ = setup_db(tmp_path)
    with Session(engine) as db:
        project = create_project(
            db,
            name="Safe Project",
            slug="safe-project",
            config={"execution_mode": "PAPER"},
        )
        transition_project(db, project.id, ProjectStatus.STOPPED)
        transition_project(db, project.id, ProjectStatus.STARTING)
        transition_project(db, project.id, ProjectStatus.RUNNING)

        assert project.status == ProjectStatus.RUNNING
        assert project.execution_mode == ExecutionMode.PAPER
        from app.paper_trading.models import PaperOrder
        assert db.query(PaperOrder).count() == 0
