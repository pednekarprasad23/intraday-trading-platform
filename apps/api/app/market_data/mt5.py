"""Read a bounded local snapshot; no network or terminal commands flow upstream."""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.auth import require_user
from app.config import get_settings


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Status(Record):
    connected: bool
    orders_available: Literal[False]
    provenance: Literal["MT5_TERMINAL"]
    observed_at: AwareDatetime


class Account(Record):
    currency: str
    balance: Decimal
    equity: Decimal
    profit: Decimal
    margin: Decimal
    free_margin: Decimal
    provenance: Literal["MT5_TERMINAL"]
    observed_at: AwareDatetime


class Position(Record):
    symbol: str
    side: Literal["BUY", "SELL", "UNKNOWN"]
    volume: Decimal
    price_open: Decimal
    price_current: Decimal
    profit: Decimal
    opened_at: AwareDatetime


class Deal(Record):
    symbol: str
    type: int
    volume: Decimal
    price: Decimal
    profit: Decimal
    time: AwareDatetime


class Tick(Record):
    symbol: str
    event_time: AwareDatetime
    received_at: AwareDatetime
    bid: Decimal
    ask: Decimal
    provenance: Literal["MT5_TERMINAL"]


class Snapshot(Record):
    observed_at: AwareDatetime
    status: Status
    account: Account | None
    positions: list[Position] | None = Field(max_length=1000)
    history: list[Deal] | None = Field(max_length=1000)
    quotes: list[Tick] = Field(max_length=20)
    errors: list[
        Literal[
            "account unavailable",
            "positions unavailable",
            "history unavailable",
            "quote unavailable",
        ]
    ]


router = APIRouter(prefix="/api/v1/mt5", dependencies=[Depends(require_user)])


def read_snapshot():
    settings = get_settings()
    unavailable = {
        "quality": "UNAVAILABLE",
        "orders_available": False,
        "snapshot": None,
    }
    if not settings.mt5_snapshot_path:
        return unavailable
    try:
        with Path(settings.mt5_snapshot_path).open("rb") as source:
            raw = source.read(2_000_001)
        if len(raw) > 2_000_000:
            return unavailable
        data = Snapshot.model_validate_json(raw)
        age = (datetime.now(timezone.utc) - data.observed_at).total_seconds()
        if age < 0 or age >= 45 or not data.status.connected:
            return {**unavailable, "quality": "STALE" if age >= 45 else "UNAVAILABLE"}
        result = data.model_dump(mode="json")
        for quote in result["quotes"]:
            event = datetime.fromisoformat(quote["event_time"])
            quote_age = (datetime.now(timezone.utc) - event).total_seconds()
            quote["quality"] = "FRESH" if 0 <= quote_age < 45 else "STALE"
        return {
            "quality": "FRESH",
            "orders_available": False,
            "age_seconds": age,
            "snapshot": result,
        }
    except (OSError, ValueError, TypeError):
        return unavailable


@router.get("/snapshot")
def current_snapshot():
    return read_snapshot()
