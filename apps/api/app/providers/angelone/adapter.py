"""Offline Angel One boundary. No SDK, credentials, network, or order access."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.market_data.contracts import Quote


class AngelOneOfflineAdapter:
    name = "ANGELONE"

    def __init__(self, token_to_instrument: dict[str, UUID]):
        self.token_to_instrument = dict(token_to_instrument)

    def normalize_ltp(self, payload: dict, received_at: datetime) -> Quote:
        """Translate only explicitly supplied price units; never guess scaling."""
        token = str(payload["symboltoken"])
        if token not in self.token_to_instrument:
            raise ValueError("Unknown instrument token")
        if received_at.tzinfo is None:
            raise ValueError("Receipt timestamp must be aware")
        event_time = payload["event_time"]
        if not isinstance(event_time, datetime) or event_time.tzinfo is None:
            raise ValueError("Provider event time must be verified and aware")
        if payload.get("price_unit") != "INR":
            raise ValueError("Unverified provider price unit")
        return Quote(
            instrument_id=self.token_to_instrument[token],
            provider=self.name,
            provider_key=token,
            event_time=event_time.astimezone(timezone.utc),
            received_at=received_at.astimezone(timezone.utc),
            last_price=Decimal(str(payload["ltp"])),
            provenance="BROKER_FIXTURE",
        )
