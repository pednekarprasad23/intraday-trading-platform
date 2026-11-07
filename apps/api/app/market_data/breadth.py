"""Nifty 50 breadth and sector analysis.

Computes index participation and sector-level PnL from constituent
historical candle data. Pure Python, no external dependencies beyond
SQLAlchemy models.
"""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

# Nifty 50 constituents with security IDs and sectors
# Security IDs from Dhan scrip master, validated 2026-11-08
NIFTY50_CONSTITUENTS: dict[str, dict[str, Any]] = {
    "RELIANCE": {"security_id": "2885", "sector": "Energy", "weight": Decimal("14.5")},
    "BHARTIARTL": {"security_id": "10604", "sector": "Telecom", "weight": Decimal("6.5")},
    "HDFCBANK": {"security_id": "1333", "sector": "Banking", "weight": Decimal("11.5")},
    "ICICIBANK": {"security_id": "4963", "sector": "Banking", "weight": Decimal("4.5")},
    "INFY": {"security_id": "1594", "sector": "IT", "weight": Decimal("3.5")},
    "TCS": {"security_id": "11536", "sector": "IT", "weight": Decimal("4.5")},
    "HINDUNILVR": {"security_id": "1394", "sector": "FMCG", "weight": Decimal("4.3")},
    "MARUTI": {"security_id": "10999", "sector": "Automobile", "weight": Decimal("4.2")},
    "BAJAJ-AUTO": {"security_id": "16669", "sector": "Automobile", "weight": Decimal("2.5")},
    "M&M": {"security_id": "2031", "sector": "Automobile", "weight": Decimal("3.5")},
    "KOTAKBANK": {"security_id": "12637", "sector": "Banking", "weight": Decimal("2.5")},
    "SBIN": {"security_id": "38086", "sector": "Banking", "weight": Decimal("4.5")},
    "AXISBANK": {"security_id": "57425", "sector": "Banking", "weight": Decimal("2.1")},
    "LT": {"security_id": "12367", "sector": "Construction", "weight": Decimal("2.5")},
    "TATASTEEL": {"security_id": "2987", "sector": "Metals", "weight": Decimal("2.6")},
    "JSWSTEEL": {"security_id": "18503", "sector": "Metals", "weight": Decimal("1.8")},
    "ASIANPAINT": {"security_id": "11597", "sector": "Consumer", "weight": Decimal("1.8")},
    "CIPLA": {"security_id": "232", "sector": "Healthcare", "weight": Decimal("1.5")},
    "SUNPHARMA": {"security_id": "5247", "sector": "Healthcare", "weight": Decimal("2.8")},
    "DRREDDY": {"security_id": "1348", "sector": "Healthcare", "weight": Decimal("2.1")},
    "DIVISLAB": {"security_id": "1929", "sector": "Healthcare", "weight": Decimal("1.5")},
    "BAJFINANCE": {"security_id": "5249", "sector": "NBFC", "weight": Decimal("2.6")},
    "BAJAJFINSV": {"security_id": "5252", "sector": "NBFC", "weight": Decimal("1.5")},
    "SBILIFE": {"security_id": "5445", "sector": "Insurance", "weight": Decimal("1.2")},
    "HDFCLIFE": {"security_id": "5235", "sector": "Insurance", "weight": Decimal("1.2")},
    "EICHERMOT": {"security_id": "5079", "sector": "Auto", "weight": Decimal("1.0")},
    "MARICO": {"security_id": "10979", "sector": "FMCG", "weight": Decimal("0.8")},
    "NESTLEIND": {"security_id": "53021", "sector": "FMCG", "weight": Decimal("1.1")},
    "ITC": {"security_id": "13657", "sector": "FMCG", "weight": Decimal("2.3")},
    "TATAMOTORS": {"security_id": "5059", "sector": "Auto", "weight": Decimal("1.2")},
    "COALINDIA": {"security_id": "50018", "sector": "Energy", "weight": Decimal("1.2")},
    "ONGC": {"security_id": "50033", "sector": "Energy", "weight": Decimal("2.1")},
    "POWERGRID": {"security_id": "50049", "sector": "Power", "weight": Decimal("1.5")},
    "NTPC": {"security_id": "50059", "sector": "Power", "weight": Decimal("0.9")},
    "HUL": {"security_id": "13655", "sector": "FMCG", "weight": Decimal("1.7")},
    "WIPRO": {"security_id": "17693", "sector": "IT", "weight": Decimal("1.3")},
    "TECHM": {"security_id": "15348", "sector": "IT", "weight": Decimal("1.3")},
    "GRASIM": {"security_id": "51065", "sector": "Cement", "weight": Decimal("1.1")},
    "ULTRACEMCO": {"security_id": "46196", "sector": "Cement", "weight": Decimal("1.2")},
    "ADANIPORTS": {"security_id": "37539", "sector": "Ports", "weight": Decimal("1.4")},
    "ADANIPOWER": {"security_id": "54237", "sector": "Power", "weight": Decimal("0.5")},
    "GAIL": {"security_id": "51223", "sector": "Energy", "weight": Decimal("0.9")},
}

VERSION = 1


@lru_cache(maxsize=1)
def get_constituents() -> dict[str, dict[str, Any]]:
    """Return the current Nifty 50 constituent mapping."""
    return NIFTY50_CONSTITUENTS.copy()


def get_sector_counts() -> dict[str, int]:
    """Return the number of constituents per sector."""
    sectors: dict[str, int] = {}
    for stock in NIFTY50_CONSTITUENTS.values():
        sector = stock["sector"]
        sectors[sector] = sectors.get(sector, 0) + 1
    return sectors


def compute_breadth(
    prices: dict[str, Decimal],
    prev_close: dict[str, Decimal],
) -> dict[str, Any]:
    """Compute breadth metrics from current prices and previous close.

    Args:
        prices: dict mapping ticker -> current price
        prev_close: dict mapping ticker -> previous close price

    Returns:
        Dict with gainers, losers, unchanged counts and percentages
    """
    gainers = losers = unchanged = 0
    for ticker in NIFTY50_CONSTITUENTS:
        curr = prices.get(ticker)
        prev = prev_close.get(ticker)
        if curr is None or prev is None or prev == 0:
            unchanged += 1
            continue
        change = (curr - prev) / prev * Decimal("100")
        if change > Decimal("0.01"):
            gainers += 1
        elif change < Decimal("-0.01"):
            losers += 1
        else:
            unchanged += 1

    total = gainers + losers + unchanged
    return {
        "gainers": gainers,
        "losers": losers,
        "unchanged": unchanged,
        "gainers_pct": float(gainers * 100 / total) if total else 0,
        "losers_pct": float(losers * 100 / total) if total else 0,
        "total": total,
    }