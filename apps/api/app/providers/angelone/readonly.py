"""Offline-only Angel One fixture normalization boundary.

The active outbound-only worker is isolated in services/angelone_worker.
No provider SDK or order methods enter the API process.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.market_data.contracts import Quote


class AngelOneReadOnlyClient:
    name = "ANGELONE"

    def __init__(self, token_to_instrument: dict[str, UUID]):
        self.token_to_instrument = dict(token_to_instrument)

    def normalize_ltp(
        self, token: str, price: str, event_time: datetime, received_at: datetime
    ) -> Quote:
        instrument_id = self.token_to_instrument.get(str(token))
        if instrument_id is None:
            raise ValueError("Unknown instrument token")
        if event_time.tzinfo is None or received_at.tzinfo is None:
            raise ValueError("Angel One timestamps must be timezone-aware")
        try:
            value = Decimal(str(price))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("Angel One LTP is invalid") from exc
        return Quote(
            instrument_id=instrument_id,
            provider=self.name,
            provider_key=str(token),
            event_time=event_time.astimezone(timezone.utc),
            received_at=received_at.astimezone(timezone.utc),
            last_price=value,
            provenance="BROKER_FIXTURE",
        )
