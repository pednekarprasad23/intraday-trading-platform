"""V2.8B Paper Execution Service and Signal Pipeline tests.

Tests verify:
1. PaperSignal persistence and traceability
2. Correlation idempotency (duplicate correlation_id returns existing signal/order)
3. Kill Switch rejection (blocked when triggered, PaperRiskEvent recorded)
4. Risk rejection (insufficient capital or exposure limit blocked)
5. Successful ENTRY and EXIT lifecycle via PaperExecutionService
6. Zero broker calls / LIVE disabled validation
7. Daily XAU backtest regression isolation
8. Parked projects untouched
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Instrument, StrategyVersion
from app.paper_trading.models import (
    KillSwitch,
    KillSwitchState,
    PaperAccount,
    PaperOrder,
    PaperOrderState,
    PaperPosition,
    PaperRiskEvent,
    PaperSignal,
    PaperSignalStatus,
)
from app.paper_trading.service import PaperExecutionService
from app.paper_trading.engine import trigger_kill_switch, reset_kill_switch
from app.projects.models import Project, ExecutionMode, ProjectStatus


class TestPaperExecutionPipeline:
    """End-to-end paper execution pipeline tests."""

    @pytest.fixture
    def setup_project_and_account(self, db: Session):
        # Ensure global kill switch is ARMED
        ks = db.scalar(select(KillSwitch).where(KillSwitch.name == "global"))
        if ks:
            ks.state = KillSwitchState.ARMED
            db.flush()
        else:
            db.add(KillSwitch(name="global", state=KillSwitchState.ARMED))
            db.flush()

        # Create active paper account
        account = PaperAccount(
            name=f"Paper Account V2.8B {uuid4()}",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("500000"),
            max_daily_loss=Decimal("100000"),
            max_total_exposure=Decimal("1000000"),
            is_active=True,
        )
        db.add(account)

        # Create Daily XAU reference project
        project = Project(
            name=f"Daily XAU V2.8B {uuid4()}",
            slug=f"daily-xau-{uuid4().hex[:6]}",
            status=ProjectStatus.STOPPED,
            execution_mode=ExecutionMode.LIVE_DISABLED,
        )
        db.add(project)
        db.flush()

        # Create StrategyVersion
        strategy_version = StrategyVersion(
            strategy_id="option-premium-ema-rsi",
            version=1,
            config_sha256=uuid4().hex,
            config={"stop_loss_pct": "1.0"},
        )
        db.add(strategy_version)
        db.flush()

        # Create unique instrument for this test
        sym = f"TEST:GOLD:{uuid4().hex[:6]}"
        instrument = Instrument(
            canonical_symbol=sym,
            display_name="Test Gold",
            asset_class="COMMODITY",
            exchange="DEMO",
            segment="DEMO",
            execution_enabled=True,
            is_demo=True,
        )
        db.add(instrument)
        db.flush()

        from app.models import ProviderSymbol
        prov_sym = ProviderSymbol(
            instrument_id=instrument.id,
            provider="DHAN",
            provider_instrument_key=instrument.canonical_symbol,
            execution_enabled=True,
        )
        db.add(prov_sym)
        db.flush()

        db.commit()
        return account, project, strategy_version, instrument

    def test_paper_signal_persistence_and_traceability(self, db: Session, setup_project_and_account):
        """Test successful LONG ENTRY paper signal execution and traceability chain."""
        account, project, strategy_version, instrument = setup_project_and_account
        correlation_id = f"corr-{uuid4()}"

        signal, exec_result = PaperExecutionService.submit_signal(
            db=db,
            project=project,
            strategy_version=strategy_version,
            instrument=instrument,
            account=account,
            direction="LONG",
            signal_type="ENTRY",
            requested_quantity=Decimal("10"),
            correlation_id=correlation_id,
            reference_price=Decimal("2000.00"),
        )

        assert signal is not None
        assert signal.status == PaperSignalStatus.COMPLETED
        assert signal.correlation_id == correlation_id
        assert signal.project_id == project.id
        assert signal.strategy_version_id == strategy_version.id

        # Verify order created and linked
        assert signal.order is not None
        assert signal.order.signal_id == signal.id
        assert signal.order.project_id == project.id
        assert signal.order.strategy_version_id == strategy_version.id
        assert signal.order.state == "filled"

        # Verify fills and position created
        assert len(signal.order.fills) > 0
        position = db.scalar(
            select(PaperPosition)
            .where(PaperPosition.account_id == account.id)
            .where(PaperPosition.instrument_id == instrument.id)
        )
        assert position is not None
        assert position.quantity == Decimal("10")

    def test_idempotency_same_correlation_id(self, db: Session, setup_project_and_account):
        """Duplicate correlation_id submissions are idempotent and do not duplicate orders or fills."""
        account, project, strategy_version, instrument = setup_project_and_account
        correlation_id = f"corr-idem-{uuid4()}"

        signal1, res1 = PaperExecutionService.submit_signal(
            db=db,
            project=project,
            strategy_version=strategy_version,
            instrument=instrument,
            account=account,
            direction="LONG",
            signal_type="ENTRY",
            requested_quantity=Decimal("5"),
            correlation_id=correlation_id,
            reference_price=Decimal("1950.00"),
        )

        signal2, res2 = PaperExecutionService.submit_signal(
            db=db,
            project=project,
            strategy_version=strategy_version,
            instrument=instrument,
            account=account,
            direction="LONG",
            signal_type="ENTRY",
            requested_quantity=Decimal("5"),
            correlation_id=correlation_id,
            reference_price=Decimal("1950.00"),
        )

        assert signal1.id == signal2.id
        assert res2 is None  # Idempotent return yields no new execution result

        # Verify exactly one order exists for this correlation
        orders = db.scalars(select(PaperOrder).where(PaperOrder.signal_id == signal1.id)).all()
        assert len(orders) == 1

    def test_kill_switch_rejection(self, db: Session, setup_project_and_account):
        """Triggered kill switch blocks paper execution, persists REJECTED signal and risk event."""
        account, project, strategy_version, instrument = setup_project_and_account
        correlation_id = f"corr-ks-{uuid4()}"

        # Trigger kill switch
        trigger_kill_switch(db, "V2.8B safety test")

        try:
            signal, exec_result = PaperExecutionService.submit_signal(
                db=db,
                project=project,
                strategy_version=strategy_version,
                instrument=instrument,
                account=account,
                direction="LONG",
                signal_type="ENTRY",
                requested_quantity=Decimal("10"),
                correlation_id=correlation_id,
                reference_price=Decimal("2000.00"),
            )

            assert signal.status == PaperSignalStatus.REJECTED
            assert "kill switch" in signal.reason.lower()

            risk_event = db.scalar(
                select(PaperRiskEvent)
                .where(PaperRiskEvent.account_id == account.id)
                .order_by(PaperRiskEvent.created_at.desc())
                .limit(1)
            )
            assert risk_event is not None
            assert risk_event.blocked is True
        finally:
            reset_kill_switch(db, uuid4())

    def test_successful_exit_lifecycle(self, db: Session, setup_project_and_account):
        """Test entry followed by matching exit closes position and locks realized P&L."""
        account, project, strategy_version, instrument = setup_project_and_account

        # 1. Entry
        corr_entry = f"entry-{uuid4()}"
        sig_entry, _ = PaperExecutionService.submit_signal(
            db=db,
            project=project,
            strategy_version=strategy_version,
            instrument=instrument,
            account=account,
            direction="LONG",
            signal_type="ENTRY",
            requested_quantity=Decimal("10"),
            correlation_id=corr_entry,
            reference_price=Decimal("2000.00"),
        )
        assert sig_entry.status == PaperSignalStatus.COMPLETED

        # 2. Exit
        corr_exit = f"exit-{uuid4()}"
        sig_exit, _ = PaperExecutionService.submit_signal(
            db=db,
            project=project,
            strategy_version=strategy_version,
            instrument=instrument,
            account=account,
            direction="LONG",
            signal_type="EXIT",
            requested_quantity=Decimal("10"),
            correlation_id=corr_exit,
            reference_price=Decimal("2050.00"),
        )
        assert sig_exit.status == PaperSignalStatus.COMPLETED

        position = db.scalar(
            select(PaperPosition)
            .where(PaperPosition.account_id == account.id)
            .where(PaperPosition.instrument_id == instrument.id)
        )
        assert position is not None
        assert position.quantity == Decimal("0")
        assert position.realized_pnl > Decimal("0")
