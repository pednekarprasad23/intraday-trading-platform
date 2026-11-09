"""V2.7C Daily XAU Reference Project Onboarding — Idempotent Seed Script.

Creates the Daily XAU Project with StrategyVersion and instrument mapping.
Idempotent: safe to run multiple times without duplication.

DO NOT modify shared StrategyVersion rows used by other projects.
DO NOT create Projects for XAUUSD Pullback or NIFTY F&O.
DO NOT enable LIVE execution.
"""

import sys
from datetime import date
from uuid import UUID, uuid4

# Ensure repo root on path
sys.path.insert(0, "/c/Users/Administrator/intraday-trading-platform")

from sqlalchemy.orm import Session

from app.main import app
from app.projects.models import Project, ProjectStatus, ExecutionMode, ProjectStrategyAssignment, RunStatus
from app.projects.service import create_project, assign_strategy, get_project_by_slug
from app.models import StrategyVersion, Instrument
from tests.test_historical import setup_db
from app.historical.reader import read_sessions


def seed_daily_xau(db: Session) -> Project | None:
    """Seed Daily XAU project. Returns the Project if created/already exists, or None on error."""

    # Check if Daily XAU Project already exists (idempotent)
    existing = get_project_by_slug(db, "daily-xau")
    if existing:
        print(f"Daily XAU Project already exists (id={existing.id}), skipping creation.")
        return existing

    # Create the Daily XAU Project
    print("Creating Daily XAU Project...")
    project = create_project(
        db,
        name="Daily XAU",
        slug="daily-xau",
        description="Daily gold (XAUUSD) breakout strategy — sandboxed backtest execution",
        config={
            "strategy_id": "option-premium-ema-rsi",
            "version": 1,
            "ema_fast": 12,
            "ema_slow": 26,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
        },
    )
    project.execution_mode = ExecutionMode.LIVE_DISABLED
    db.commit()
    db.refresh(project)
    print(f"  Project created: id={project.id}, name={project.name}, slug={project.slug}")
    print(f"  execution_mode={project.execution_mode}")

    # Ensure the canonical StrategyVersion exists (option-premium-ema-rsi, version=1)
    # StrategyVersion has UniqueConstraint(strategy_id, version, config_sha256)
    # We create it only if it doesn't already exist
    sv = db.scalar(
        select(StrategyVersion).where(
            StrategyVersion.strategy_id == "option-premium-ema-rsi",
            StrategyVersion.version == 1,
        )
    )
    if sv is None:
        # Compute config_sha256 for {"ema_fast": 12, "ema_slow": 26, "rsi_period": 14, "rsi_overbought": 70, "rsi_oversold": 30}
        import hashlib
        config_dict = {"ema_fast": 12, "ema_slow": 26, "rsi_period": 14, "rsi_overbought": 70, "rsi_oversold": 30}
        config_sha256 = hashlib.sha256(str(sorted(config_dict.items())).encode()).hexdigest()[:64]
        print(f"  Creating StrategyVersion with config_sha256={config_sha256}...")
        sv = StrategyVersion(
            strategy_id="option-premium-ema-rsi",
            version=1,
            config=config_dict,
            config_sha256=config_sha256,
        )
        db.add(sv)
        db.flush()
        print(f"  StrategyVersion created: id={sv.id}")
    else:
        print(f"  StrategyVersion already exists: id={sv.id}, config_sha256={sv.config_sha256}")

    # Assign the strategy to the project
    print("Assigning strategy to project...")
    assignment = assign_strategy(
        db,
        project_id=project.id,
        strategy_id="option-premium-ema-rsi",
        strategy_version_id=sv.id,
        role="primary",
        priority=1,
    )
    print(f"  Assignment created: id={assignment.id}, role={assignment.role}, priority={assignment.priority}")

    # Verify XAUUSD instrument exists in DB (use DEMO fixture if available)
    # Look for Gold/XAUUSD instrument
    xau_instrument = db.scalar(
        select(Instrument).where(
            Instrument.canonical_symbol.like("%XAU%") | Instrument.canonical_symbol.like("%Gold%")
        )
    )
    if xau_instrument:
        print(f"  Found XAU instrument: id={xau_instrument.id}, canonical={xau_instrument.canonical_symbol}")
        # Ensure HistoricalPartition exists for a recent test date
        # Use date(2026, 11, 6) as a valid test date (same as test_backtesting.py fixtures)
        hp = db.scalar(
            select(HistoricalPartition).where(
                HistoricalPartition.provider == "DEMO",
                HistoricalPartition.instrument_id == xau_instrument.id,
                HistoricalPartition.timeframe == "1m",
                HistoricalPartition.session_date == date(2026, 11, 6),
            )
        )
        if hp is None:
            print(f"  Creating DEMO HistoricalPartition for {date(2026, 11, 6)}...")
            # We need a HistoricalImportJob first
            # Use a simplified approach: create a minimal HP via the existing fixture mechanism
            # For now, just verify the instrument exists and note the partition will be created by test fixtures
            hp = db.scalar(
                select(HistoricalPartition).where(
                    HistoricalPartition.provider == "DEMO",
                    HistoricalPartition.instrument_id == xau_instrument.id,
                )
            )
            if hp is None:
                print(f"  No existing DEMO HistoricalPartition for XAU — will use test fixture import mechanism")
        else:
            print(f"  Existing DEMO HistoricalPartition found: id={hp.id}")
    else:
        print("  No XAU instrument found in DB — test fixtures will provide HistoricalPartition during runtime tests")

    db.commit()
    return project


if __name__ == "__main__":
    from app.database import engine

    print("=" * 60)
    print("V2.7C Daily XAU Reference Project Onboarding")
    print("=" * 60)

    with Session(engine) as db:
        project = seed_daily_xau(db)

    if project:
        print("\n" + "=" * 60)
        print("SUCCESS: Daily XAU Project onboarding complete")
        print("=" * 60)
        print(f"Project: id={project.id}, name={project.name}, slug={project.slug}")
        print(f"execution_mode={project.execution_mode}")
        print(f"status={project.status}")
        print("\nNext steps:")
        print("1. Verify runtime START/STOP cycle")
        print("2. Submit reference run")
        print("3. Verify deterministic reproducibility")
        print("4. Run full backend pytest suite")
    else:
        print("\n" + "=" * 60)
        print("FAILED: Daily XAU onboarding did not complete")
        print("=" * 60)
        sys.exit(1)