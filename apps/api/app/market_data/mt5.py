"""MT5 provider bridge — local terminal snapshot reader.

This module connects to a local MetaTrader 5 terminal via its Python API
or reads a bounded snapshot file.  It supports:

  - Gold (XAUUSD) — spot gold CFD, 24/5 trading
  - Bitcoin (BTCUSD) — crypto CFD, 24/7 trading
  - Any other MT5 symbol mapped in the instrument master

No order execution flows through this module; it is read-only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.auth import require_user
from app.config import get_settings
from app.instruments.mappings import MT5_SYMBOLS


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


# ---------------------------------------------------------------------------
# MT5-specific routes
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/mt5", dependencies=[Depends(require_user)])


def _read_snapshot():
    """Read bounded MT5 snapshot from file. No network, no terminal."""
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
            return {
                **unavailable,
                "quality": "STALE" if age >= 45 else "UNAVAILABLE",
            }
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
    """Read the latest MT5 terminal snapshot (read-only)."""
    return _read_snapshot()


# ---------------------------------------------------------------------------
# MT5 contract metadata
# ---------------------------------------------------------------------------


class MT5ContractInfo(BaseModel):
    """Verified MT5 contract specification."""

    canonical_symbol: str
    mt5_symbol: str
    description: str
    lot_size: Decimal
    point_value: Decimal
    tick_size: Decimal
    pip_value: Decimal
    currency: str
    trading_hours: str
    timezone: str
    digits: int
    margin_initial: str
    margin_maintenance: str
    swap_long: Decimal
    swap_short: Decimal


@router.get("/contracts", response_model=list[MT5ContractInfo])
def mt5_contract_specs():
    """Return verified MT5 contract specifications for Gold and Bitcoin.

    All values are broker-dependent defaults; operator must verify
    against the actual MT5 broker configuration.
    """
    specs: list[MT5ContractInfo] = []
    for canonical, info in MT5_SYMBOLS.items():
        specs.append(
            MT5ContractInfo(
                canonical_symbol=canonical,
                mt5_symbol=info["symbol"],
                description=info["description"],
                lot_size=info["contract_size"],
                point_value=info["point_value"],
                tick_size=info["tick_size"],
                pip_value=info["pip_value"],
                currency="USD",
                trading_hours=info["trading_hours"],
                timezone=info["timezone"],
                digits=info["digits"],
                margin_initial=info["margin_initial"],
                margin_maintenance=info["margin_maintenance"],
                swap_long=Decimal(str(info["swap_long"])),
                swap_short=Decimal(str(info["swap_short"])),
            )
        )
    return specs


@router.get("/contracts/{canonical_symbol}", response_model=MT5ContractInfo)
def mt5_contract_spec(canonical_symbol: str):
    """Return MT5 contract spec for a single canonical symbol."""
    info = MT5_SYMBOLS.get(canonical_symbol)
    if info is None:
        return {"error": "Not found"}
    return MT5ContractInfo(
        canonical_symbol=canonical_symbol,
        mt5_symbol=info["symbol"],
        description=info["description"],
        lot_size=info["contract_size"],
        point_value=info["point_value"],
        tick_size=info["tick_size"],
        pip_value=info["pip_value"],
        currency="USD",
        trading_hours=info["trading_hours"],
        timezone=info["timezone"],
        digits=info["digits"],
        margin_initial=info["margin_initial"],
        margin_maintenance=info["margin_maintenance"],
        swap_long=Decimal(str(info["swap_long"])),
        swap_short=Decimal(str(info["swap_short"])),
    )


# ---------------------------------------------------------------------------
# MT5 quote endpoint — maps MT5 ticks to provider-independent Quote
# ---------------------------------------------------------------------------


class MT5Quote(Record):
    """Provider-independent quote projected from MT5 tick."""

    model_config = ConfigDict(extra="forbid")

    canonical_symbol: str
    mt5_symbol: str
    bid: Decimal
    ask: Decimal
    mid: Decimal
    spread: Decimal
    event_time: AwareDatetime
    received_at: AwareDatetime
    provenance: Literal["MT5_TERMINAL"]


@router.get("/quotes", response_model=list[MT5Quote])
def mt5_quotes(limit: int = Query(20, ge=1, le=100)):
    """Return latest MT5 ticks as provider-independent quotes.

    Only reads the snapshot file; never contacts the terminal directly.
    """
    snap = _read_snapshot()
    if snap.get("snapshot") is None:
        return []
    quotes: list[MT5Quote] = []
    for tick in snap["snapshot"]["quotes"][:limit]:
        mt5_sym = tick["symbol"]
        bid = Decimal(str(tick["bid"]))
        ask = Decimal(str(tick["ask"]))
        mid = (bid + ask) / Decimal(2)
        spread = ask - bid

        # Look up canonical symbol
        canonical = None
        for canon, info in MT5_SYMBOLS.items():
            if info["symbol"] == mt5_sym:
                canonical = canon
                break

        quotes.append(
            MT5Quote(
                canonical_symbol=canonical or mt5_sym,
                mt5_symbol=mt5_sym,
                bid=bid,
                ask=ask,
                mid=mid,
                spread=spread,
                event_time=datetime.fromisoformat(tick["event_time"]),
                received_at=datetime.fromisoformat(tick["received_at"]),
            )
        )
    return quotes
