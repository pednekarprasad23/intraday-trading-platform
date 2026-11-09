"""Authenticated, bounded read-only Angel One snapshot publication."""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.auth import require_user
from app.config import get_settings


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AngelQuote(Record):
    symbol: str = Field(min_length=1, max_length=64)
    ltp: Decimal
    event_time: AwareDatetime | None
    received_at: AwareDatetime
    provenance: Literal["ANGEL_ONE"]

    @field_validator("ltp")
    @classmethod
    def positive_price(cls, price: Decimal) -> Decimal:
        if not price.is_finite() or price <= 0:
            raise ValueError("LTP must be positive and finite")
        return price


class AngelSnapshot(Record):
    observed_at: AwareDatetime
    provider: Literal["ANGEL_ONE"]
    authenticated: bool
    quotes: list[AngelQuote] = Field(max_length=20)
    errors: list[Literal["authentication unavailable", "quote unavailable"]] = Field(
        max_length=20
    )
    orders_available: Literal[False]


router = APIRouter(prefix="/api/v1/angelone", dependencies=[Depends(require_user)])


def read_snapshot():
    unavailable = {
        "quality": "UNAVAILABLE",
        "orders_available": False,
        "snapshot": None,
    }
    settings = get_settings()
    path = settings.angelone_snapshot_path
    if not settings.angelone_enabled or not path:
        return unavailable
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(1_000_001)
        if len(raw) > 1_000_000:
            return unavailable
        snapshot = AngelSnapshot.model_validate_json(raw)
        age = (datetime.now(timezone.utc) - snapshot.observed_at).total_seconds()
        if age < -5 or age >= 45 or not snapshot.authenticated:
            return {**unavailable, "quality": "STALE" if age >= 45 else "UNAVAILABLE"}
        result = snapshot.model_dump(mode="json")
        for quote in result["quotes"]:
            event = quote["event_time"]
            quote_age = (
                (
                    datetime.now(timezone.utc) - datetime.fromisoformat(event)
                ).total_seconds()
                if event
                else None
            )
            quote["quality"] = (
                ("FRESH" if quote_age < 45 else "STALE")
                if quote_age is not None and quote_age >= 0
                else "UNVERIFIED_EVENT_TIME"
            )
        return {
            "quality": (
                "FRESH"
                if result["quotes"]
                and all(q["quality"] == "FRESH" for q in result["quotes"])
                else "STALE"
                if any(q["quality"] == "STALE" for q in result["quotes"])
                else "UNVERIFIED"
            ),
            "orders_available": False,
            "age_seconds": age,
            "snapshot": result,
        }
    except (OSError, ValueError, TypeError):
        return unavailable


@router.get("/snapshot")
def current_snapshot():
    return read_snapshot()
