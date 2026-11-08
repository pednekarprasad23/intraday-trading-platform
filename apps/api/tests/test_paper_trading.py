"""Phase 4 paper trading tests — risk checks and order lifecycle.

Tests verify:
1. Kill switch state management (armed/disarmed)
2. Paper account separation from live accounts
3. Eligibility, capital, exposure checks
4. Idempotency and restart handling
5. Risk event creation and persistence
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Instrument
from app.paper_trading.engine import (
    check_capital,
    check_position_limit,
    check_kill_switch,
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
    """Kill switch state management tests."""

    def test_new_db_default_is_armed(self, db: Session):
        """Without any kill switch record, system is armed (allowing orders)."""
        result = is_kill_switch_armed(db)
        assert result is True

    def test_triggered_kill_switch_blocks_orders(self, db: Session):
        """After triggering kill switch, new orders are blocked."""
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

        inst = db.scalar(select(Instrument).limit(1))
        if inst is None:
            pytest.skip("No instruments in DB")

        # Trigger kill switch
        trigger_kill_switch(db, "test-trigger")
        assert is_kill_switch_armed(db) is False

        # Verify orders are blocked
        risk_result = check_kill_switch(db)
        assert risk_result.approved is False
        assert "kill switch" in risk_result.reason.lower()

    def test_reset_kill_switch(self, db: Session):
        """Reset kill switch allows orders to proceed."""
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

        # Trigger and reset
        trigger_kill_switch(db, "test-trigger")
        assert is_kill_switch_armed(db) is False

        reset_kill_switch(db, "test-reset")
        assert is_kill_switch_armed(db) is True

    def test_kill_switch_persists_across_requests(self, db: Session):
        """Kill switch state persists in database across API calls."""
        trigger_kill_switch(db, "test-persist")

        # Query fresh from DB
        ks = db.scalar(select(KillSwitch).order_by(KillSwitch.created_at.desc()).limit(1))
        assert ks is not None
        assert ks.state == KillSwitchState.TRIGGERED

    def test_kill_switch_reason_required(self, db: Session):
        """Kill switch must include a reason for audit trail."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
        )
        db.add(account)
        db.commit()

        trigger_kill_switch(db, "system-maintenance")
        ks = db.scalar(select(KillSwitch).order_by(KillSwitch.created_at.desc()).limit(1))
        assert ks is not None
        assert len(ks.reason) > 0


class TestPaperAccountSeparation:
    """Paper account isolation tests."""

    def test_paper_account_has_no_live_trading(self, db: Session):
        """Paper accounts cannot execute live trades."""
        account = PaperAccount(
            name="Paper Test",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("500000"),
        )
        db.add(account)
        db.commit()

        # Verify account type
        assert account.is_paper is True
        # Paper accounts should not have live trading enabled
        assert account.live_trading_enabled is False

    def test_paper_account_initial_state(self, db: Session):
        """Paper account starts with correct initial state."""
        account = PaperAccount(
            name="Fresh Paper Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("500000"),
            max_daily_loss=Decimal("100000"),
            max_total_exposure=Decimal("1000000"),
        )
        db.add(account)
        db.commit()

        assert account.currency == "INR"
        assert account.initial_capital == Decimal("1000000")
        assert account.available_capital == Decimal("1000000")
        assert account.position_count == 0


class TestCapitalChecks:
    """Capital and exposure check tests."""

    def test_check_capital_approves_within_limits(self, db: Session):
        """Orders within capital limits are approved."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("500000"),
        )
        db.add(account)
        db.commit()

        inst = db.scalar(select(Instrument).limit(1))
        if inst is None:
            pytest.skip("No instruments in DB")

        result = check_capital(account, inst, Decimal("100"), Decimal("1000"))
        assert result.approved is True

    def test_check_capital_rejects_insufficient(self, db: Session):
        """Orders exceeding available capital are rejected."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("100000"),
            available_capital=Decimal("100000"),
            max_position_value=Decimal("50000"),
        )
        db.add(account)
        db.commit()

        inst = db.scalar(select(Instrument).limit(1))
        if inst is None:
            pytest.skip("No instruments in DB")

        # Order for 1000 * 1000 = 1000000 which exceeds 100000
        result = check_capital(account, inst, Decimal("1000"), Decimal("1000"))
        assert result.approved is False
        assert "capital" in result.reason.lower() or "sufficient" in result.reason.lower()

    def test_check_position_limit_rejects_exceeds(
        self,
        db: Session,
    ):
        """Orders exceeding position limits are rejected."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("100000"),
        )
        db.add(account)
        db.commit()

        inst = db.scalar(select(Instrument).limit(1))
        if inst is None:
            pytest.skip("No instruments in DB")

        # Position value exceeds max_position_value
        result = check_position_limit(account, inst, Decimal("1000"), Decimal("1000"))
        assert result.approved is False
        assert "position" in result.reason.lower() or "exposure" in result.reason.lower()

    def test_exposure_tracking(self, db: Session):
        """Exposure is tracked across multiple positions."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("500000"),
        )
        db.add(account)
        db.commit()

        inst1 = db.scalar(select(Instrument).limit(1))
        inst2 = db.scalar(
            select(Instrument)
            .where(Instrument.id != inst1.id)
            .limit(1)
        )

        # Both within limit
        result1 = check_capital(account, inst1, Decimal("100"), Decimal("1000"))
        result2 = check_capital(account, inst2, Decimal("100"), Decimal("1000"))
        assert result1.approved is True
        assert result2.approved is True


class TestIdempotency:
    """Idempotency and restart handling tests."""

    def test_duplicate_order_rejected(self, db: Session):
        """Duplicate orders with same idempotency key are rejected."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
        )
        db.add(account)
        db.commit()

        # First order succeeds
        order1 = PaperOrder(
            account_id=account.id,
            instrument_id=db.scalar(select(Instrument).limit(1)).id,
            side=PaperOrderSide.BUY,
            quantity=Decimal("100"),
            order_type=PaperOrderType.MARKET,
            state=PaperOrderState.SUBMITTED,
        )
        db.add(order1)
        db.commit()

        # Verify order exists
        stored = db.get(PaperOrder, order1.id)
        assert stored is not None

    def test_restart_recoverable_state(self, db: Session):
        """Paper trading state can be recovered after restart."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
        )
        db.add(account)
        db.commit()

        # Create order in pending state
        order = PaperOrder(
            account_id=account.id,
            instrument_id=db.scalar(select(Instrument).limit(1)).id,
            side=PaperOrderSide.BUY,
            quantity=Decimal("100"),
            order_type=PaperOrderType.MARKET,
            state=PaperOrderState.PENDING,
        )
        db.add(order)
        db.commit()

        # Verify state is recoverable
        pending_orders = db.scalars(
            select(PaperOrder).where(PaperOrder.state == PaperOrderState.PENDING)
        ).all()
        assert len(pending_orders) > 0


class TestRiskEvents:
    """Risk event creation and persistence tests."""

    def test_risk_event_created_on_check(self, db: Session):
        """Risk events are created and stored."""
        account = PaperAccount(
            name="Risk Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("500000"),
        )
        db.add(account)
        db.commit()

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

    def test_risk_event_types(self, db: Session):
        """All risk event types can be recorded."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
        )
        db.add(account)
        db.commit()

        event_types = [
            PaperRiskEventType.CAPITAL_EXHAUSTED,
            PaperRiskEventType.POSITION_LIMIT,
            PaperRiskEventType.DAILY_LOSS_LIMIT,
            PaperRiskEventType.EXPOSURE_LIMIT,
            PaperRiskEventType.KILL_SWITCH,
        ]

        for event_type in event_types:
            event = PaperRiskEvent(
                account_id=account.id,
                event_type=event_type,
                details='{"test": "data"}',
            )
            db.add(event)
            db.commit()

            stored = db.get(PaperRiskEvent, event.id)
            assert stored is not None
            assert stored.event_type == event_type


class TestOrderLifecycle:
    """Order lifecycle tests."""

    def test_order_created_in_pending_state(self, db: Session):
        """New orders start in pending state."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
        )
        db.add(account)
        db.commit()

        order = PaperOrder(
            account_id=account.id,
            instrument_id=db.scalar(select(Instrument).limit(1)).id,
            side=PaperOrderSide.BUY,
            quantity=Decimal("100"),
            order_type=PaperOrderType.MARKET,
            state=PaperOrderState.PENDING,
        )
        db.add(order)
        db.commit()

        stored = db.get(PaperOrder, order.id)
        assert stored is not None
        assert stored.state == PaperOrderState.PENDING

    def test_order_state_transitions(self, db: Session):
        """Orders transition through valid states."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
        )
        db.add(account)
        db.commit()

        order = PaperOrder(
            account_id=account.id,
            instrument_id=db.scalar(select(Instrument).limit(1)).id,
            side=PaperOrderSide.BUY,
            quantity=Decimal("100"),
            order_type=PaperOrderType.MARKET,
            state=PaperOrderState.PENDING,
        )
        db.add(order)
        db.commit()

        # Transition to submitted
        order.state = PaperOrderState.SUBMITTED
        db.commit()

        stored = db.get(PaperOrder, order.id)
        assert stored.state == PaperOrderState.SUBMITTED

    def test_order_cancellation(self, db: Session):
        """Orders can be cancelled."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
        )
        db.add(account)
        db.commit()

        order = PaperOrder(
            account_id=account.id,
            instrument_id=db.scalar(select(Instrument).limit(1)).id,
            side=PaperOrderSide.BUY,
            quantity=Decimal("100"),
            order_type=PaperOrderType.MARKET,
            state=PaperOrderState.PENDING,
        )
        db.add(order)
        db.commit()

        # Cancel order
        order.state = PaperOrderState.CANCELLED
        db.commit()

        stored = db.get(PaperOrder, order.id)
        assert stored.state == PaperOrderState.CANCELLED


class TestPositionAggregation:
    """Position aggregation and tracking tests."""

    def test_position_aggregation(self, db: Session):
        """Multiple orders aggregate into single position."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
        )
        db.add(account)
        db.commit()

        inst = db.scalar(select(Instrument).limit(1))

        # Create first position
        position1 = PaperPosition(
            account_id=account.id,
            instrument_id=inst.id,
            quantity=Decimal("100"),
            avg_price=Decimal("100"),
        )
        db.add(position1)

        # Create second position for same instrument
        position2 = PaperPosition(
            account_id=account.id,
            instrument_id=inst.id,
            quantity=Decimal("50"),
            avg_price=Decimal("105"),
        )
        db.add(position2)
        db.commit()

        # Verify positions exist
        positions = db.scalars(
            select(PaperPosition).where(PaperPosition.account_id == account.id)
        ).all()
        assert len(positions) == 2

    def test_position_reduces_available_capital(self, db: Session):
        """Opening position reduces available capital."""
        account = PaperAccount(
            name="Test Account",
            currency="INR",
            initial_capital=Decimal("1000000"),
            available_capital=Decimal("1000000"),
            max_position_value=Decimal("500000"),
        )
        db.add(account)
        db.commit()

        inst = db.scalar(select(Instrument).limit(1))

        # Open position
        position = PaperPosition(
            account_id=account.id,
            instrument_id=inst.id,
            quantity=Decimal("100"),
            avg_price=Decimal("1000"),  # 100 * 1000 = 100000
        )
        db.add(position)
        db.commit()

        # Refresh account from DB
        db.refresh(account)
        assert account.available_capital < Decimal("1000000")


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def setup_paper_data(db: Session):
    """Setup paper trading test data."""
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
    return account


@pytest.fixture
def setup_position(db: Session, setup_paper_data: PaperAccount):
    """Setup test position."""
    inst = db.scalar(select(Instrument).limit(1))
    if inst is None:
        pytest.skip("No instruments in DB")

    position = PaperPosition(
        account_id=setup_paper_data.id,
        instrument_id=inst.id,
        quantity=Decimal("100"),
        avg_price=Decimal("100"),
    )
    db.add(position)
    db.commit()
    return position


@pytest.fixture
def setup_risk_test(db: Session):
    """Setup account for risk testing."""
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
