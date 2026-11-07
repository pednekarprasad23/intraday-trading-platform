"""Instrument master — Phase 3 expanded with indexes, equities, futures, MT5.

This module provides:
  - Phase 3 instrument specifications (indexes, stocks, futures, MT5)
  - Provider configurations for DHAN, AngelOne, MT5
  - Symbol mapping utilities

Usage:
    from app.instruments import mappings as phase3

    # Access index specs
    niftybank = phase3.NIFTYBANK
    banknifty_fut = phase3.BANKNIFTY_FUT

    # Access MT5 contracts
    gold = phase3.MT5_GOLD
    btc = phase3.MT5_BTC

    # Access provider tokens
    token_info = phase3.DHAN_NSE_INDEX_TOKENS["DEMO:NIFTY"]
"""

__all__ = [
    "mappings",
]

from app.instruments import mappings