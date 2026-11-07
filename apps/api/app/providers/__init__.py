"""Provider registry — broker and data-source configuration.

Each provider entry declares:
  - name: canonical provider key (uppercase)
  - ptype: 'broker', 'data', or 'bridge'
  - supported_asset_classes: list of asset classes this provider handles
  - supported_exchanges: list of exchanges
  - requires_credentials: bool
  - api_base: base URL or connection string
  - rate_limits: per-second and per-minute limits (None = unknown)
  - timezone: primary trading timezone
  - market_hours: dict of session windows per day-of-week (0=Mon)
  - instrument_types: list of instrument types this provider supports
  - metadata: provider-specific notes

Usage:
    from app.providers import DHAN, ANGELONE, MT5, get_provider

    # Get provider config
    config = get_provider("DHAN")
    # config.api_base -> "https://api.dhan.co"
    # config.timezone -> "Asia/Kolkata"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ProviderType = Literal["broker", "data", "bridge"]
InstrumentType = Literal["INDEX", "EQUITY", "FUTURES", "OPTION", "COMMODITY", "CRYPTO"]


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    ptype: ProviderType
    supported_asset_classes: list[str]
    supported_exchanges: list[str]
    requires_credentials: bool
    api_base: str
    rate_limits: dict[str, int | None] = field(default_factory=dict)
    timezone: str = "UTC"
    market_hours: dict[str, tuple[str, str]] = field(default_factory=dict)
    instrument_types: list[InstrumentType] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Provider definitions
# ---------------------------------------------------------------------------

DHAN = ProviderConfig(
    name="DHAN",
    ptype="broker",
    supported_asset_classes=["INDEX", "EQUITY", "FUTURES", "OPTION", "COMMODITY"],
    supported_exchanges=["NSE", "BSE", "MCX"],
    requires_credentials=True,
    api_base="https://api.dhan.co",
    rate_limits={"per_second": 5, "per_minute": 120},
    timezone="Asia/Kolkata",
    market_hours={
        "0": ("09:15", "15:30"),  # Mon
        "1": ("09:15", "15:30"),  # Tue
        "2": ("09:15", "15:30"),  # Wed
        "3": ("09:15", "15:30"),  # Thu
        "4": ("09:15", "15:30"),  # Fri
    },
    instrument_types=["INDEX", "EQUITY", "FUTURES", "OPTION"],
    metadata={
        "broker_type": "discount_broker",
        "segment_access": ["EQ", "CO", "BO", "MARGIN", "FUTEXX", "INDEXFUT", "INDEXOPTN"],
        "settlement_cycle": "T+1",
        "api_docs": "https://developers.dhan.co",
        "phase": 1,
    },
)

ANGELONE = ProviderConfig(
    name="ANGELONE",
    ptype="broker",
    supported_asset_classes=["INDEX", "EQUITY", "FUTURES", "OPTION"],
    supported_exchanges=["NSE", "BSE"],
    requires_credentials=True,
    api_base="https://api.angelbroking.com",
    rate_limits={"per_second": 3, "per_minute": 60},
    timezone="Asia/Kolkata",
    market_hours={
        "0": ("09:15", "15:30"),
        "1": ("09:15", "15:30"),
        "2": ("09:15", "15:30"),
        "3": ("09:15", "15:30"),
        "4": ("09:15", "15:30"),
    },
    instrument_types=["INDEX", "EQUITY", "FUTURES", "OPTION"],
    metadata={
        "broker_type": "full_service",
        "segment_access": ["EQ", "CD", "BO", "CO", "MF", "BCD"],
        "settlement_cycle": "T+1",
        "api_docs": "https://developers.angelbroking.com",
        "phase": 1,
    },
)

MT5 = ProviderConfig(
    name="MT5",
    ptype="bridge",
    supported_asset_classes=["COMMODITY", "CRYPTO", "FOREX", "INDEX"],
    supported_exchanges=["MT5"],
    requires_credentials=False,
    api_base="local_socket",
    rate_limits={"per_second": None, "per_minute": None},
    timezone="UTC",
    market_hours={
        "0": ("22:00", "22:00"),   # Sun 22:00 UTC – Fri 22:00 UTC (Forex/Gold)
        "1": ("22:00", "22:00"),
        "2": ("22:00", "22:00"),
        "3": ("22:00", "22:00"),
        "4": ("22:00", "22:00"),
        "5": ("22:00", "22:00"),
        "6": ("00:00", "23:59"),   # Crypto 24/7
    },
    instrument_types=["COMMODITY", "CRYPTO", "FOREX", "INDEX"],
    metadata={
        "platform": "MetaTrader 5",
        "connection": "local_terminal",
        "contract_types": ["CFD", "SPOT"],
        "leverage_available": True,
        "swap_enabled": True,
        "phase": 3,
        "notes": (
            "MT5 bridge reads local terminal via socket. "
            "Gold (XAUUSD) trades 24/5; Bitcoin (BTCUSD) trades 24/7. "
            "Lot sizes, point values and margin are broker-dependent. "
            "Operator must verify actual MT5 broker symbol names."
        ),
    },
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, ProviderConfig] = {
    DHAN.name: DHAN,
    ANGELONE.name: ANGELONE,
    MT5.name: MT5,
}


def get_provider(name: str) -> ProviderConfig | None:
    return PROVIDERS.get(name.upper())


def list_providers() -> list[ProviderConfig]:
    return list(PROVIDERS.values())
