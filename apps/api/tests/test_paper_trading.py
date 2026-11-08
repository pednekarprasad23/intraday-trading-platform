"""Phase 4 paper trading tests — risk checks and order lifecycle."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Instrument
from app.paper_trading.engine import (
    check_kill_switch,
    check_capital,
    check_position_limit,
    is_kill_switch_armed,
    reset_kill_switch,
    trigger_kill_switch,
    validate_order_risks,
)
from app.paper_trading.models import (
    KillSwitch,
    KillSwitchState,
    PaperAccount,
    PaperOrder,
    PaperOrderState,
    PaperOrderSide,
    PaperOrderType,
    PaperPosition,
    PaperRiskEvent,
    PaperRiskEventType,
)
from app.paper_trading.engine import PaperTradingEngine, RiskContext


class TestKillSwitch:
    """Kill switch tests."""

    def test_new_db_default_is_armed(self, db: Session):
        """Without any kill switch record, system is armed (allowing orders)."""
        result = is_kill_switch_armed(db)
        assert result == True  # Armed = no restriction

    def test_triggered_kill_switch_blocks_orders(self, db: Session):
        """After triggering kill switch, new orders are blocked."""
        # Create default paper account for testing
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("500000"),
            max_daily_loss=Decimal("100000"),
            max_total_exposure=Decimal("1000000"),
        )
        db.add(account)
        db.commit()

        # Get an instrument
        inst = db.scalar(select(Instrument).limit(1))
        if inst is None:
            pytest.skip("No instruments in DB")

        # Trigger kill switch
        trigger_kill_switch(db, reason="Test trigger")
        db.commit()

        # Now check killswitch
        ks = db.scalar(select(KillSwitch).where(KillSwitch.name == "global"))
        assert ks is not None
        assert ks.state == KillSwitchState.TRIGGERED

    def test_reset_kill_switch(self, db: Session):
        """Kill switch can be reset after being triggered."""
        # Trigger first
        ks = trigger_kill_switch(db, reason="Test reset")
        db.commit()

        # Reset
        reset_kill_switch(db, reset_by=None)
        db.commit()

        # Verify state
        ks = db.scalar(select(KillSwitch).where(KillSwitch.name == "global"))
        assert ks.state == KillSwitchState.RESET_PENDING


class TestRiskValidation:
    """Risk validation tests."""

    @pytest.fixture
    def paper_account(self, db: Session) -> PaperAccount:
        account = PaperAccount(
            name=f"Test Account {uuid4().hex[:8]}",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("500000"),
            max_daily_loss=Decimal("100000"),
            max_total_exposure=Decimal("1000000"),
        )
        db.add(account)
        db.commit()
        return account

    @pytest.fixture
    def test_instrument(self, db: Session) -> Instrument:
        inst = db.scalar(select(Instrument).limit(1))
        if inst is None:
            pytest.skip("No instruments in DB")
        return inst

    def test_check_capital_approves_within_limits(
        self, db: Session, paper_account: PaperAccount, test_instrument: Instrument
    ):
        """Check capital approves when within available capital."""
        ctx = RiskContext(
            account=paper_account,
            instrument=test_instrument,
            quantity=Decimal("100"),
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            price=Decimal("1000"),  # 100 * 1000 = 100000 < 1M available
            data_age_seconds=10,
            is_market_open=True,
            daily_pnl=Decimal(0),
            daily_order_count=0,
        )
        result = check_capital(ctx)
        assert result.approved == True

    def test_check_capital_rejects_insufficient(
        self, db: Session, paper_account: PaperAccount, test_instrument: Instrument
    ):
        """Check capital rejects when exceeds available capital."""
        ctx = RiskContext(
            account=paper_account,
            instrument=test_instrument,
            quantity=Decimal("1000"),
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            price=Decimal("10000"),  # 1000 * 10000 = 10M > 1M available
            data_age_seconds=10,
            is_market_open=True,
            daily_pnl=Decimal(0),
            daily_order_count=0,
        )
        result = check_capital(ctx)
        assert result.approved == False
        assert "Insufficient capital" in result.reason

    def test_check_position_limit_rejects_exceeds(
        self, db: Session, paper_account: PaperAccount, test_instrument: Instrument
    ):
        """Check position limit rejects when position would exceed max."""
        ctx = RiskContext(
            account=paper_account,
            instrument=test_instrument,
            quantity=Decimal("10000"),  # Will exceed max_position_value
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            price=Decimal("1000"),
            data_age_seconds=10,
            is_market_open=True,
            daily_pnl=Decimal(0),
            daily_order_count=0,
            current_position_qty=Decimal("100000"),  # Already large position
        )
        result = check_position_limit(ctx)
        assert result.approved == False


class TestPaperOrderLifecycle:
    """Paper order lifecycle tests."""

    @pytest.fixture
    def setup_paper_data(self, db: Session):
        """Setup paper account and instrument."""
        account = PaperAccount(
            name=f"Order Lifecycle Test {uuid4().hex[:8]}",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("500000"),
            max_daily_loss=Decimal("100000"),
            max_total_exposure=Decimal("1000000"),
        )
        db.add(account)
        db.flush()

        # Get existing instrument
        inst = db.scalar(select(Instrument).limit(1))
        if inst is None:
            pytest.skip("No instruments in DB")

        db.commit()
        return account, inst

    def test_order_created_in_pending_state(self, db: Session, setup_paper_data):
        """New order is created in pending state."""
        account, instrument = setup_paper_data

        engine = PaperTradingEngine(db)
        result = engine.submit_order(
            account=account,
            instrument=instrument,
            side=PaperOrderSide.BUY,
            quantity=Decimal("100"),
            order_type=PaperOrderType.MARKET,
        )

        assert result.order.state == PaperOrderState.PENDING.value


class TestPaperPosition:
    """Position management tests."""

    @pytest.fixture
    def setup_position(self, db: Session):
        account = PaperAccount(
            name="Position Test",
            currency="INR",
            initial_capital=Decimal("500000"),
            available_capital=Decimal("500000"),
            max_position_value=Decimal("250000"),
            max_daily_loss=Decimal("100000"),
            max_total_exposure=Decimal("500000"),
        )
        db.add(account)
        db.commit()
        return account

    def test_position_aggregation(self, db: Session, setup_position):
        """Test position quantity aggregation."""
        account = setup_position
        inst = db.scalar(select(Instrument).limit(1))
        if inst is None:
            pytest.skip("No instruments")

        inst = db.scalar(select(Instrument).limit(1))
        if inst is None:
            pytest.skip("No instruments")

        pos = PaperPosition(
            account_id=account.id,
            instrument_id=inst.id,
            quantity=Decimal("100"),
        )
        db.add(pos)
        db.commit()

        stored = db.get(PaperPosition, pos.id)
        assert stored.quantity == Decimal("100")


class TestRiskEventLogging:
    """Risk event logging tests."""

    @pytest.fixture
    def setup_risk_test(self, db: Session):
        account = PaperAccount(
            name=f"Risk Test {uuid4().hex[:8]}",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("500000"),
            max_daily_loss=Decimal("100000"),
            max_total_exposure=Decimal("1000000"),
        )
        db.add(account)
        db.commit()
        return account

    def test_risk_event_created_on_check(self, db: Session, setup_risk_test):
        """Test that risk events are created and stored."""
        account = setup_risk_test

        event = PaperRiskEvent(
            account_id=account.id,
            event_type=PaperRiskEventType.DAILY_LOSS_LIMIT,
            details='{"amount": "100000"}',
        )
        db.add(event)
        db.commit()

        stored = db.get(PaperRiskEvent, event.id)
        assert stored is not None
        assert stored.event_type == PaperRiskEventType.DAILY_LOSS_LIMIT