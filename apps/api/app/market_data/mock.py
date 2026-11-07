"""Scripted provider; never generates purported market observations."""

from collections import deque
from dataclasses import dataclass
from uuid import UUID

from app.market_data.contracts import MarketDataProvider, Quote


@dataclass(frozen=True)
class Disconnect:
    reason: str = "scripted disconnect"


@dataclass(frozen=True)
class Heartbeat:
    pass


class MockProvider(MarketDataProvider):
    name = "MOCK"

    def __init__(self, events: list[Quote | Disconnect | Heartbeat]):
        self.events = deque(events)
        self.subscriptions: set[UUID] = set()
        self.closed = False
        self.heartbeats = 0

    def subscribe(self, instrument_ids: set[UUID]) -> None:
        self.subscriptions.update(instrument_ids)

    def unsubscribe(self, instrument_ids: set[UUID]) -> None:
        self.subscriptions.difference_update(instrument_ids)

    def next_event(self) -> Quote | None:
        if self.closed:
            raise RuntimeError("Provider is closed")
        if not self.events:
            return None
        event = self.events.popleft()
        if isinstance(event, Disconnect):
            raise ConnectionError(event.reason)
        if isinstance(event, Heartbeat):
            self.heartbeats += 1
            return None
        if event.instrument_id not in self.subscriptions:
            raise ValueError("Unmapped or unsubscribed instrument")
        return event

    def close(self) -> None:
        self.closed = True
