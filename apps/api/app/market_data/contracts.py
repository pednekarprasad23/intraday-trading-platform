"""Provider-independent, read-only market-data contracts."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class FeedState(StrEnum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    BACKING_OFF = "backing_off"
    AUTH_FAILED = "auth_failed"


class Quality(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    OUT_OF_ORDER = "out_of_order"


@dataclass(frozen=True)
class Quote:
    instrument_id: UUID
    provider: str
    provider_key: str
    event_time: datetime
    received_at: datetime
    last_price: Decimal
    sequence: str | None = None
    provenance: str = "DEMO"

    def __post_init__(self):
        for timestamp in (self.event_time, self.received_at):
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("Market timestamps must be timezone-aware")
        if not self.last_price.is_finite() or self.last_price <= 0:
            raise ValueError("Price must be positive and finite")
        if not self.provider or not self.provider_key:
            raise ValueError("Provider identity is required")

    def as_public(self) -> dict:
        return {
            "instrument_id": str(self.instrument_id),
            "provider": self.provider,
            "event_time": self.event_time.astimezone(timezone.utc).isoformat(),
            "received_at": self.received_at.astimezone(timezone.utc).isoformat(),
            "last_price": str(self.last_price),
            "provenance": self.provenance,
        }


class MarketDataProvider(Protocol):
    name: str

    def subscribe(self, instrument_ids: set[UUID]) -> None: ...

    def unsubscribe(self, instrument_ids: set[UUID]) -> None: ...

    def next_event(self) -> Quote | None: ...

    def close(self) -> None: ...
