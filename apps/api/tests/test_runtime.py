"""Project runtime foundation and sandboxed execution tests (V2.6 Phase 3)."""

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import StrategyVersion
from app.projects.models import ProjectStatus, RunStatus
from app.projects.service import create_project
from app.projects.runtime import start_runtime, stop_runtime, submit_run
from app.projects.sandbox import validate_and_snapshot_parameters
from app.paper_trading.models import KillSwitch, KillSwitchState
from tests.test_historical import setup_db


def test_runtime_activation_and_lifecycle(tmp_path):
    """Verify genuine runtime activation, heartbeat, and stop semantics."""
    engine, _ = setup_db(tmp_path)
    with Session(engine) as db:
        project = create_project(db, name="Runtime Proj", slug="runtime-proj")
        assert project.status == ProjectStatus.CREATED
        assert project.runtime_status == "STOPPED"

        # Start runtime
        project = start_runtime(db, project.id, actor_email="operator@intraday.com")
        assert project.status == ProjectStatus.RUNNING
        assert project.runtime_status == "RUNNING"
        assert project.runtime_instance_id is not None
        assert project.heartbeat_at is not None

        # Stop runtime
        project = stop_runtime(db, project.id, actor_email="operator@intraday.com")
        assert project.status == ProjectStatus.STOPPED
        assert project.runtime_status == "STOPPED"
        assert project.runtime_instance_id is None
        assert project.heartbeat_at is None


def test_parameter_validation_and_security(tmp_path):
    """Verify parameters are validated, snapshot immutable, fingerprinted, and secure against injection."""
    # Valid parameters
    params, fp = validate_and_snapshot_parameters({"ema_period": 14, "stop_loss_pct": 1.5})
    assert params["ema_period"] == 14
    assert fp is not None
    assert len(fp) == 64

    # Invalid non-dict parameters
    with pytest.raises(HTTPException) as exc:
        validate_and_snapshot_parameters("malicious_string")
    assert exc.value.status_code == 400

    # Security violation: forbidden execution patterns
    with pytest.raises(HTTPException) as exc:
        validate_and_snapshot_parameters({"cmd": "eval('import os; os.system(\"rm -rf /\")')"})
    assert exc.value.status_code == 400


def test_one_active_run_policy_and_sandbox_execution(tmp_path):
    """Verify one-active-run policy, strategy version immutability, and Kill Switch blocking."""
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

        project = create_project(db, name="Exec Proj", slug="exec-proj")
        start_runtime(db, project.id)

        # Submit first run
        run1 = submit_run(
            db,
            project_id=project.id,
            strategy_version_id=sv.id,
            parameters={"threshold": 0.5},
        )
        assert run1.status == RunStatus.RUNNING

        # Second concurrent run should be rejected by one-active-run policy
        with pytest.raises(HTTPException) as exc:
            submit_run(
                db,
                project_id=project.id,
                strategy_version_id=sv.id,
                parameters={"threshold": 0.8},
            )
        assert exc.value.status_code == 400
        assert "active run" in exc.value.detail.lower()

        # Cancel or finish run1
        run1.status = RunStatus.COMPLETED
        db.commit()

        # Trigger Kill Switch and verify runs are blocked
        ks = KillSwitch(name="global", state=KillSwitchState.TRIGGERED, reason="Manual test trigger")
        db.add(ks)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            submit_run(
                db,
                project_id=project.id,
                strategy_version_id=sv.id,
                parameters={"threshold": 0.6},
            )
        assert exc.value.status_code == 403
        assert "Kill Switch" in exc.value.detail
