"""Clock-injected freshness tracking and bounded reconnect policy."""

import random
import time
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID

from app.market_data.contracts import FeedState, Quality, Quote


class FeedMonitor:
    def __init__(
        self,
        timeout_seconds: float = 30,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        if timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        self.timeout_seconds = timeout_seconds
        self.clock = clock
        self.wall_clock = wall_clock
        self.state = FeedState.STOPPED
        self.heartbeat_at: float | None = None
        self.last_quote: dict[UUID, tuple[Quote, float]] = {}
        self.subscriptions: set[UUID] = set()
        self.attempts = 0

    def connected(self):
        self.state = FeedState.CONNECTED
        self.heartbeat_at = self.clock()

    def heartbeat(self):
        if self.state == FeedState.CONNECTED:
            self.heartbeat_at = self.clock()

    def receive(self, quote: Quote) -> Quality:
        if (
            self.state != FeedState.CONNECTED
            or quote.instrument_id not in self.subscriptions
        ):
            return Quality.UNAVAILABLE
        current = self.last_quote.get(quote.instrument_id)
        if current and quote.event_time <= current[0].event_time:
            return Quality.OUT_OF_ORDER
        # Arrival does not rescue a provider timestamp that was already stale.
        now = self.wall_clock()
        if (
            quote.event_time > now
            or quote.received_at > now
            or (now - quote.event_time).total_seconds() >= self.timeout_seconds
        ):
            return Quality.STALE
        self.last_quote[quote.instrument_id] = (quote, self.clock())
        return Quality.FRESH

    def quality(self, instrument_id: UUID) -> Quality:
        if self.state != FeedState.CONNECTED:
            return Quality.UNAVAILABLE
        quote = self.last_quote.get(instrument_id)
        if not quote:
            return Quality.UNAVAILABLE
        if (
            self.clock() - quote[1] >= self.timeout_seconds
            or (self.wall_clock() - quote[0].event_time).total_seconds()
            >= self.timeout_seconds
        ):
            return Quality.STALE
        return Quality.FRESH

    def disconnected(self, authentication_failure: bool = False):
        if self.state in {
            FeedState.STOPPED,
            FeedState.BACKING_OFF,
            FeedState.AUTH_FAILED,
        }:
            return
        self.last_quote.clear()
        self.state = (
            FeedState.AUTH_FAILED if authentication_failure else FeedState.BACKING_OFF
        )
        self.heartbeat_at = None
        if not authentication_failure:
            self.attempts += 1

    def retry_delay(
        self, jitter: Callable[[float, float], float] = random.uniform
    ) -> float:
        if self.state != FeedState.BACKING_OFF:
            raise ValueError("Not retrying")
        maximum = min(60.0, 2 ** min(self.attempts - 1, 6))
        return jitter(maximum / 2, maximum)

    def heartbeat_quality(self) -> Quality:
        if self.state != FeedState.CONNECTED or self.heartbeat_at is None:
            return Quality.UNAVAILABLE
        return (
            Quality.STALE
            if self.clock() - self.heartbeat_at >= self.timeout_seconds
            else Quality.FRESH
        )

    def stop(self):
        self.state = FeedState.STOPPED
        self.heartbeat_at = None
