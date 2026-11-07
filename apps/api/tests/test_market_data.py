from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.instruments.sync import MasterEntry, import_master
from app.market_data.contracts import FeedState, Quality, Quote
from app.market_data.feed import FeedMonitor
from app.market_data.mock import Disconnect, Heartbeat, MockProvider
from app.models import Base, Instrument, ProviderSymbol
from app.providers.angelone.adapter import AngelOneOfflineAdapter


def sample_quote(instrument_id, now):
    return Quote(instrument_id, "MOCK", "DEMO:1", now, now, Decimal("100.01"))


def test_mock_and_freshness():
    instrument = uuid4()
    now = datetime.now(timezone.utc)
    time = [0.0]
    wall = [now]
    quote = sample_quote(instrument, now)
    provider = MockProvider([Heartbeat(), quote, Disconnect()])
    provider.subscribe({instrument})
    monitor = FeedMonitor(10, lambda: time[0], lambda: wall[0])
    monitor.subscriptions.add(instrument)
    monitor.connected()
    assert provider.next_event() is None
    monitor.heartbeat()
    assert monitor.receive(provider.next_event()) == Quality.FRESH
    assert monitor.receive(quote) == Quality.OUT_OF_ORDER
    time[0] = 10
    wall[0] += timedelta(seconds=10)
    assert monitor.quality(instrument) == Quality.STALE
    assert monitor.heartbeat_quality() == Quality.STALE
    with pytest.raises(ConnectionError):
        provider.next_event()
    monitor.disconnected()
    assert monitor.state == FeedState.BACKING_OFF
    assert monitor.retry_delay(lambda lower, upper: upper) == 1
    monitor.connected()
    assert monitor.quality(instrument) == Quality.UNAVAILABLE
    monitor.disconnected(authentication_failure=True)
    with pytest.raises(ValueError):
        monitor.retry_delay()
    monitor.stop()
    provider.close()


def test_reject_bad_market_events():
    instrument = uuid4()
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        Quote(instrument, "MOCK", "1", now.replace(tzinfo=None), now, Decimal("1"))
    with pytest.raises(ValueError):
        Quote(instrument, "MOCK", "1", now, now, Decimal("NaN"))
    clock = [now]
    monitor = FeedMonitor(5, lambda: 0, lambda: clock[0])
    monitor.subscriptions.add(instrument)
    monitor.connected()
    assert (
        monitor.receive(sample_quote(instrument, now + timedelta(seconds=1)))
        == Quality.STALE
    )
    assert (
        monitor.receive(sample_quote(instrument, now - timedelta(seconds=5)))
        == Quality.STALE
    )
    assert monitor.quality(instrument) == Quality.UNAVAILABLE


def test_offline_angelone_requires_verified_units():
    instrument = uuid4()
    now = datetime.now(timezone.utc)
    adapter = AngelOneOfflineAdapter({"123": instrument})
    payload = {"symboltoken": "123", "ltp": "12.25", "event_time": now}
    with pytest.raises(ValueError, match="price unit"):
        adapter.normalize_ltp(payload, now)
    payload["price_unit"] = "INR"
    assert adapter.normalize_ltp(payload, now).last_price == Decimal("12.25")
    payload["symboltoken"] = "unknown"
    with pytest.raises(ValueError, match="Unknown"):
        adapter.normalize_ltp(payload, now)


def test_master_import_is_idempotent_and_refuses_collision(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'master.db'}")
    Base.metadata.create_all(engine)
    entry = MasterEntry("DEMO:ONE", "One", "INDEX", "NSE", "DEMO", "MOCK", "1", "NSE")
    with Session(engine) as db:
        assert import_master(db, [entry]) == {"created": 1, "updated": 0}
        db.commit()
        assert import_master(db, [entry]) == {"created": 0, "updated": 1}
        db.commit()
        assert db.scalar(
            select(Instrument).where(Instrument.canonical_symbol == "DEMO:ONE")
        ).is_demo
        assert db.scalar(select(ProviderSymbol)).execution_enabled is False
        with pytest.raises(ValueError, match="collision"):
            import_master(
                db,
                [
                    MasterEntry(
                        "DEMO:TWO", "Two", "INDEX", "NSE", "DEMO", "MOCK", "1", "NSE"
                    )
                ],
            )
        db.rollback()
        assert (
            db.scalar(
                select(Instrument).where(Instrument.canonical_symbol == "DEMO:TWO")
            )
            is None
        )
