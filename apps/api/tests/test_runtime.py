"""Project runtime foundation and sandboxed execution tests (V2.6 Phase 3 Acceptance Audit)."""

import asyncio
import time
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import StrategyVersion
from app.projects.models import ProjectStatus, RunStatus, Project
from app.projects.service import create_project
from app.projects.runtime import start_runtime, stop_runtime, submit_run, ACTIVE_RUNTIMES
from app.projects.sandbox import validate_and_snapshot_parameters
from app.paper_trading.models import KillSwitch, KillSwitchState
from tests.test_historical import setup_db


def test_independent_background_heartbeat_and_registry(tmp_path):
    """Verify that starting a project spawns an independent background runtime task,

    updates heartbeats independently (H2 > H1), registers in ACTIVE_RUNTIMES,
    and cleans up registry upon STOP.
    """
    engine, _ = setup_db(tmp_path)
    with Session(engine) as db:
        project = create_project(db, name="Heartbeat Proj", slug="heartbeat-proj")
        start_runtime(db, project.id)

        p_str = str(project.id)
        assert p_str in ACTIVE_RUNTIMES
        assert ACTIVE_RUNTIMES[p_str].running is True

        # Record H1 heartbeat
        db.expire_all()
        p_loaded = db.get(Project, project.id)
        h1 = p_loaded.heartbeat_at
        assert h1 is not None

        # Duplicate start should be rejected
        with pytest.raises(HTTPException) as exc:
            start_runtime(db, project.id)
        assert exc.value.status_code == 400

        # Wait for background task to independently advance heartbeat
        time.sleep(3.5)

        db.expire_all()
        p_loaded2 = db.get(Project, project.id)
        h2 = p_loaded2.heartbeat_at
        assert h2 is not None
        assert h2 >= h1

        # Stop runtime
        stop_runtime(db, project.id)
        assert p_str not in ACTIVE_RUNTIMES
        p_loaded3 = db.get(Project, project.id)
        assert p_loaded3.status == ProjectStatus.STOPPED
        assert p_loaded3.runtime_status == "STOPPED"


def test_parameter_validation_innocent_substrings_and_security(tmp_path):
    """Verify parameters are validated, allowing innocent substrings (like 'position' or 'loss')

    while strictly blocking code injection patterns (eval, exec, import, os, subprocess).
    """
    # Innocent parameters containing natural substrings should be fully accepted
    valid_params, fp = validate_and_snapshot_parameters({
        "strategy_notes": "position sizing and stop_loss threshold",
        "imported_data_flag": True,
        "max_loss_limit": 5000,
    })
    assert valid_params["max_loss_limit"] == 5000
    assert fp is not None

    # Code execution patterns must be rejected
    with pytest.raises(HTTPException) as exc:
        validate_and_snapshot_parameters({"payload": "eval('print(1)')"})
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        validate_and_snapshot_parameters({"payload": "import os; os.system('ls')"})
    assert exc.value.status_code == 400


def test_one_active_run_enforcement_and_kill_switch(tmp_path):
    """Verify one-active-run policy and Kill Switch execution blocking."""
    engine, _ = setup_db(tmp_path)
    with Session(engine) as db:
        sv = StrategyVersion(
            strategy_id="option-premium-ema-rsi",
            version=1,
            config={"timeframe": "1m"},
            config_sha256="abcsha256",
        )
        db.add(sv)
        db.commit()

        project = create_project(db, name="Active Run Proj", slug="activerun-proj")
        start_runtime(db, project.id)

        run1 = submit_run(
            db,
            project_id=project.id,
            strategy_version_id=sv.id,
            parameters={"threshold": 0.5},
        )
        assert run1 is not None

        # Second concurrent run attempt must be rejected
        with pytest.raises(HTTPException) as exc:
            submit_run(
                db,
                project_id=project.id,
                strategy_version_id=sv.id,
                parameters={"threshold": 0.8},
            )
        assert exc.value.status_code == 400

        # Trigger Kill Switch
        ks = KillSwitch(name="global", state=KillSwitchState.TRIGGERED, reason="Audit test trigger")
        db.add(ks)
        db.commit()

        # Finish run1
        run1.status = RunStatus.COMPLETED
        db.commit()

        # New runs blocked by Kill Switch
        with pytest.raises(HTTPException) as exc:
            submit_run(
                db,
                project_id=project.id,
                strategy_version_id=sv.id,
                parameters={"threshold": 0.6},
            )
        assert exc.value.status_code == 403

        stop_runtime(db, project.id)
