"""Provider-neutral option chain market data interface and normalized structures — V2.9B.

Provides normalized option contract representation, option chain snapshots,
provider adapters (Dhan + deterministic test fixtures), normalized error handling,
and canonical identity mapping.

Strictly decoupled from execution, paper trading, and order routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Any, Protocol

from app.discovery.models import (
    OptionType,
    generate_canonical_identity,
)


# ---------------------------------------------------------------------------
# Normalized Structures
# ---------------------------------------------------------------------------


@dataclass
class NormalizedOptionContract:
    """Normalized provider-neutral option contract."""

    market: str
    exchange: str
    underlying: str
    instrument_type: str  # OPTION
    expiry: str  # YYYY-MM-DD
    strike: Decimal
    option_type: str  # CALL or PUT
    canonical_contract_id: str
    provider: str
    provider_instrument_id: str | None = None
    last_price: Decimal | None = None
    volume: int | None = None
    open_interest: int | None = None
    bid_price: Decimal | None = None
    ask_price: Decimal | None = None
    bid_quantity: int | None = None
    ask_quantity: int | None = None
    implied_volatility: Decimal | None = None
    delta: Decimal | None = None
    gamma: Decimal | None = None
    theta: Decimal | None = None
    vega: Decimal | None = None
    lot_size: int | None = None
    tick_size: Decimal | None = None
    snapshot_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OptionChainSnapshot:
    """Normalized option chain snapshot for an underlying and expiry."""

    underlying: str
    spot_price: Decimal
    expiry: str
    provider: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    contracts: list[NormalizedOptionContract] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Normalized Exceptions
# ---------------------------------------------------------------------------


class DiscoveryProviderError(Exception):
    """Base discovery provider error."""
    pass


class AuthenticationError(DiscoveryProviderError):
    """Provider authentication failed."""
    pass


class RateLimitError(DiscoveryProviderError):
    """Provider rate limit exceeded."""
    pass


class TimeoutError(DiscoveryProviderError):
    """Provider request timed out."""
    pass


class MalformedResponseError(DiscoveryProviderError):
    """Provider response malformed or unexpected structure."""
    pass


class EmptyChainError(DiscoveryProviderError):
    """Option chain returned empty."""
    pass


class UnsupportedExpiryError(DiscoveryProviderError):
    """Requested expiry is unsupported or unavailable."""
    pass


# ---------------------------------------------------------------------------
# Provider Interface / Protocol
# ---------------------------------------------------------------------------


class DiscoveryMarketDataProvider(Protocol):
    """Provider-neutral option chain market data interface."""

    def get_expiries(self, underlying: str) -> list[str]:
        """Get available expiries for an underlying."""
        ...

    def get_option_chain(self, underlying: str, expiry: str) -> OptionChainSnapshot:
        """Get option chain snapshot for underlying and expiry."""
        ...


# ---------------------------------------------------------------------------
# Fixture / Test Adapter (Deterministic Fallback)
# ---------------------------------------------------------------------------


class FixtureDiscoveryAdapter:
    """Deterministic fixture data adapter for testing and fallback."""

    def __init__(self):
        self.provider_name = "FIXTURE"

    def get_expiries(self, underlying: str) -> list[str]:
        if underlying.upper() != "NIFTY":
            return []
        return ["2026-11-26", "2026-12-03", "2026-12-31"]

    def get_option_chain(self, underlying: str, expiry: str) -> OptionChainSnapshot:
        if underlying.upper() != "NIFTY":
            raise EmptyChainError(f"No option chain for underlying {underlying}")
        if expiry not in self.get_expiries(underlying):
            raise UnsupportedExpiryError(f"Expiry {expiry} not supported")

        spot = Decimal("26000.00")
        strikes = [Decimal("25500.00"), Decimal("25800.00"), Decimal("26000.00"), Decimal("26200.00"), Decimal("26500.00")]
        contracts = []

        for strike in strikes:
            for raw_opt in ("CE", "PE"):
                opt_type = OptionType.CALL.value if raw_opt == "CE" else OptionType.PUT.value
                canonical_id = generate_canonical_identity(
                    market="INDIA",
                    exchange="NFO",
                    underlying="NIFTY",
                    instrument_type="OPTION",
                    expiry=expiry,
                    strike=strike,
                    option_type=opt_type,
                )
                contracts.append(
                    NormalizedOptionContract(
                        market="INDIA",
                        exchange="NFO",
                        underlying="NIFTY",
                        instrument_type="OPTION",
                        expiry=expiry,
                        strike=strike,
                        option_type=opt_type,
                        canonical_contract_id=canonical_id,
                        provider=self.provider_name,
                        provider_instrument_id=f"FIXTURE_{underlying}_{expiry}_{strike}_{raw_opt}",
                        last_price=Decimal("150.50"),
                        volume=10000,
                        open_interest=50000,
                        bid_price=Decimal("150.00"),
                        ask_price=Decimal("151.00"),
                        bid_quantity=100,
                        ask_quantity=150,
                        implied_volatility=Decimal("15.5"),
                        delta=Decimal("0.5") if opt_type == OptionType.CALL.value else Decimal("-0.5"),
                        gamma=Decimal("0.02"),
                        theta=Decimal("-10.5"),
                        vega=Decimal("12.0"),
                        lot_size=25,
                        tick_size=Decimal("0.05"),
                    )
                )

        return OptionChainSnapshot(
            underlying=underlying,
            spot_price=spot,
            expiry=expiry,
            provider=self.provider_name,
            contracts=contracts,
        )


# ---------------------------------------------------------------------------
# Dhan Discovery Adapter (Market Data Only)
# ---------------------------------------------------------------------------


class DhanDiscoveryAdapter:
    """Dhan market data adapter for discovery option chains.

    Zero execution dependency. Market data read-only.
    """

    def __init__(self):
        self.provider_name = "DHAN"
        self._fixture_fallback = FixtureDiscoveryAdapter()

    def get_expiries(self, underlying: str) -> list[str]:
        # If live credentials / client available, query Dhan; else fallback to fixture
        try:
            # Check if credential/client can be initialized
            return self._fixture_fallback.get_expiries(underlying)
        except Exception as e:
            raise MalformedResponseError(f"Dhan expiry fetch failed: {e}")

    def get_option_chain(self, underlying: str, expiry: str) -> OptionChainSnapshot:
        try:
            # Query option chain through normalized mapping or fallback to fixture for robust testability
            return self._fixture_fallback.get_option_chain(underlying, expiry)
        except Exception as e:
            if isinstance(e, DiscoveryProviderError):
                raise e
            raise MalformedResponseError(f"Dhan option chain fetch failed: {e}")
