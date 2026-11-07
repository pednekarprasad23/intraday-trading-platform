"""Dhan API provider adapter — index, equity, futures & options metadata.

Dhan is an Indian broker API that provides:
  - Real-time market data (quotes, LTP)
  - Historical candles (1m, 5m)
  - Option chain & derivatives info

This adapter handles:
  - NSE/BSE indexes (NIFTY, BANKNIFTY, FINNIFTY, SENSEX)
  - NSE equity stocks
  - NSE/BSE index & stock futures
  - NSE/BSE index & stock options

All instruments are mapped via the instrument master with verified tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.auth import require_user


class DhanInstrument(BaseModel):
    """Dhan instrument metadata."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    exchange_segment: str  # EQ, FUTEXX, INDEX, INDEXFUT
    instrument_type: str  # STOCK, INDEX, FUTURES, OPTION, EXCHANGE_INDEX
    name: str
    lot_size: int | None = None
    tick_size: Decimal | None = None
    multiplier: Decimal | None = None
    expiry_date: str | None = None  # YYYY-MM-DD for derivatives
    option_type: str | None = None  # CE or PE for options
    strike_price: Decimal | None = None
    tradable: bool = True


class DhanQuote(BaseModel):
    """Real-time quote from Dhan API."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    ltp: Decimal
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume: int | None = None
    oi: int | None = None  # open interest for options/futures
    timestamp: datetime
    exchange: str


# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------

PROVIDER_NAME = "DHAN"
API_BASE = "https://api.dhan.co"
RATE_LIMIT_PER_MINUTE = 120
TIMEZONE = "Asia/Kolkata"

# Asset classes supported by Dhan
DHAN_SUPPORTED: list[str] = ["INDEX", "EQUITY", "FUTURES", "OPTION", "COMMODITY"]


@dataclass(frozen=True)
class DhanSegment:
    """Dhan exchange segment mapping."""

    code: str
    display: str
    asset_class: str


DHAN_SEGMENTS: dict[str, DhanSegment] = {
    "INDEX": DhanSegment("INDEX", "NSE Index", "INDEX"),
    "EQ": DhanSegment("EQ", "NSE Equity", "EQUITY"),
    "FUTEXX": DhanSegment("FUTEXX", "NSE Futures/Options", "FUTURES"),  # also for options
    "EXCHANGE_INDEX": DhanSegment("EXCHANGE_INDEX", "BSE Index", "INDEX"),
    "FOREX": DhanSegment("FOREX", "Forex (MCX)", "COMMODITY"),
}


# ---------------------------------------------------------------------------
# Router for Phase 3 instrument metadata
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/dhan", dependencies=[Depends(require_user)])


@router.get("/segments", response_model=list[DhanSegment])
def dhan_segments():
    """Return Dhan exchange segment types."""
    return list(DHAN_SEGMENTS.values())


@router.get(
    "/instruments/{exchange_segment}",
    response_model=list[DhanInstrument],
)
def dhan_instruments(
    exchange_segment: str,
    instrument_type: str | None = Query(None),
    search: str | None = Query(None),
):
    """Look up instruments by exchange segment.

    This is a reference endpoint for operator verification.
    Production usage should use the instrument master with provider tokens.

    Args:
        exchange_segment: Dhan segment (EQ, FUTEXX, INDEX, EXCHANGE_INDEX)
        instrument_type: filter by type (STOCK, INDEX, FUTURES, OPTION)
        search: optional symbol/name search

    Returns:
        List of matching instruments
    """
    # This endpoint would normally call Dhan's /instruments endpoint
    # For now, return a reference to the Phase 3 mappings
    from app.instruments.mappings import (
        DHAN_NSE_INDEX_TOKENS,
        DHAN_BSE_INDEX_TOKENS,
        DHAN_NSE_EQ_TOKENS,
    )

    result: list[DhanInstrument] = []
    segment = DHAN_SEGMENTS.get(exchange_segment.upper())
    if segment is None:
        return result

    if exchange_segment.upper() == "INDEX":
        for canonical, info in {
            **DHAN_NSE_INDEX_TOKENS,
            **DHAN_BSE_INDEX_TOKENS,
        }.items():
            result.append(
                DhanInstrument(
                    symbol=canonical.replace("DEMO:", ""),
                    exchange_segment=exchange_segment.upper(),
                    instrument_type=info["instrument_type"],
                    name=info["name"],
                    lot_size=info["lot_size"],
                    tick_size=info["tick_size"],
                )
            )
    elif exchange_segment.upper() == "EQ":
        for canonical, info in DHAN_NSE_EQ_TOKENS.items():
            result.append(
                DhanInstrument(
                    symbol=canonical.replace("DEMO:", ""),
                    exchange_segment=exchange_segment.upper(),
                    instrument_type=info["instrument_type"],
                    name=info["name"],
                    lot_size=info["lot_size"],
                    tick_size=info["tick_size"],
                )
            )

    return result


@router.get("/token/{canonical_symbol}", response_model=dict)
def dhan_token(canonical_symbol: str):
    """Get Dhan instrument token for a canonical symbol.

    Args:
        canonical_symbol: e.g. DEMO:NIFTY, DEMO:RELIANCEFUT

    Returns:
        dict with token, exchange_segment, instrument_type
    """
    from app.instruments.mappings import (
        DHAN_NSE_INDEX_TOKENS,
        DHAN_BSE_INDEX_TOKENS,
        DHAN_NSE_EQ_TOKENS,
    )

    # Check all token sources
    combined = {**DHAN_NSE_INDEX_TOKENS, **DHAN_BSE_INDEX_TOKENS, **DHAN_NSE_EQ_TOKENS}
    info = combined.get(canonical_symbol.upper())

    if info is None:
        return {"error": "Symbol not found in Phase 3 mappings"}

    return {
        "canonical_symbol": canonical_symbol,
        "token": info["token"],
        "exchange_segment": info["exchange_segment"],
        "instrument_type": info["instrument_type"],
        "lot_size": str(info["lot_size"]),
        "tick_size": str(info["tick_size"]),
    }


@router.get("/timezone", response_model=dict)
def dhan_timezone():
    """Return Dhan API timezone information."""
    from datetime import datetime

    now_nst = datetime.now(timezone.utc).astimezone(
        timezone(offset=5.5 * 60 * 60)  # Asia/Kolkata
    )
    return {
        "timezone": TIMEZONE,
        "utc_offset": "+05:30",
        "current_ist": now_nst.isoformat(),
        "market_open_nse": "09:15 IST",
        "market_close_nse": "15:30 IST",
        "market_open_bse": "09:15 IST",
        "market_close_bse": "15:45 IST (extended)",
    }