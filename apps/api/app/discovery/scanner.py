"""Generic scanner interface and MarketCandidate model — V2.9C.

Provides provider-neutral MarketScanner interface, ScannerContext input contract,
and durable MarketCandidate discovery evidence model.

Strictly decoupled from execution, paper trading, and order routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID, uuid4
import hashlib

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Numeric,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.discovery.provider import OptionChainSnapshot, NormalizedOptionContract


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ScannerContext:
    """Input context required for a scan operation."""

    universe_name: str
    snapshot: OptionChainSnapshot
    timeframe: str = "1m"
    scanner_id: str = "reference-scanner"
    scanner_version: str = "1.0.0"
    as_of: datetime = field(default_factory=utcnow)


@dataclass
class CandidateEvidence:
    """Bounded extensible raw scanner metrics and evidence."""
    metrics: dict[str, Any] = field(default_factory=dict)


class MarketCandidate:
    """Provider-independent MarketCandidate discovery evidence representation."""

    def __init__(
        self,
        scanner_id: str,
        scanner_version: str,
        market: str,
        exchange: str,
        asset_class: str,
        instrument_type: str,
        underlying: str,
        discovery_reason: str,
        snapshot_at: datetime,
        canonical_contract_id: str | None = None,
        expiry: str | None = None,
        strike: Decimal | None = None,
        option_type: str | None = None,
        evidence: dict[str, Any] | None = None,
        provider: str = "DEMO",
    ):
        self.scanner_id = scanner_id
        self.scanner_version = scanner_version
        self.market = market
        self.exchange = exchange
        self.asset_class = asset_class
        self.instrument_type = instrument_type
        self.underlying = underlying
        self.discovery_reason = discovery_reason
        self.snapshot_at = snapshot_at
        self.canonical_contract_id = canonical_contract_id
        self.expiry = expiry
        self.strike = strike
        self.option_type = option_type
        self.evidence = evidence or {}
        self.provider = provider
        self.detected_at = utcnow()
        self.candidate_id = self._generate_candidate_id()

    @property
    def canonical_contract(self) -> NormalizedOptionContract:
        """Reconstruct normalized contract from canonical_contract_id components.

        Parses the canonical_contract_id (format: EXCHANGE:UNDERLYING:STRIKE:TYPE)
        and rebuilds a NormalizedOptionContract for downstream consumption.
        """
        from app.discovery.provider import NormalizedOptionContract

        # Parse canonical_contract_id: typically "NFO:NIFTY:24000:PUT" or similar
        parts = (self.canonical_contract_id or "").split(":")
        if len(parts) >= 3:
            exchange = parts[0] if parts[0] else self.exchange
            underlying = parts[1] if len(parts) > 1 else self.underlying
            strike_str = parts[2]
            option_type = parts[3] if len(parts) > 3 else (self.option_type or "PUT")
            try:
                strike = Decimal(strike_str) if strike_str else None
            except Exception:
                strike = None
        else:
            exchange = self.exchange
            underlying = self.underlying
            strike = self.strike
            option_type = self.option_type or "PUT"

        return NormalizedOptionContract(
            market=self.market,
            exchange=exchange,
            underlying=underlying,
            instrument_type=self.instrument_type,
            expiry=self.expiry or (parts[4] if len(parts) > 4 else None),
            strike=strike,
            option_type=option_type,
            canonical_contract_id=self.canonical_contract_id,
            provider=self.provider,
            provider_instrument_id=self.evidence.get("provider_instrument_id"),
            last_price=self.evidence.get("last_price"),
            volume=self.evidence.get("volume", 0),
            open_interest=self.evidence.get("open_interest", 0),
            bid_price=self.evidence.get("bid_price"),
            ask_price=self.evidence.get("ask_price"),
            implied_volatility=self.evidence.get("implied_volatility"),
            delta=self.evidence.get("delta"),
            gamma=self.evidence.get("gamma"),
            theta=self.evidence.get("theta"),
            vega=self.evidence.get("vega"),
            lot_size=self.evidence.get("lot_size", 25),
            tick_size=Decimal(str(self.evidence.get("tick_size", "0.05"))),
            snapshot_at=self.snapshot_at,
        )

    def _generate_candidate_id(self) -> str:
        """Generate deterministic candidate ID for idempotency and duplicate prevention.

        Combines scanner_id, canonical_contract_id (or underlying), discovery_reason,
        and snapshot timestamp epoch to distinguish unique observations.
        """
        raw_key = f"{self.scanner_id}:{self.canonical_contract_id or self.underlying}:{self.discovery_reason}:{int(self.snapshot_at.timestamp())}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class MarketScanner(Protocol):
    """Provider-neutral scanner abstraction interface."""

    def scan(self, context: ScannerContext) -> list[MarketCandidate]:
        """Execute scan on context and return discovered market candidates."""
        ...


class ReferenceTestScanner:
    """Reference test scanner implementation for validation and fixture testing.

    Does not contain real trading strategy logic; simply inspects normalized option chain
    and emits candidates for contracts meeting basic existence/validity criteria.
    """

    def __init__(self, scanner_id: str = "reference-test-scanner", scanner_version: str = "1.0.0"):
        self.scanner_id = scanner_id
        self.scanner_version = scanner_version

    def scan(self, context: ScannerContext) -> list[MarketCandidate]:
        candidates = []
        snapshot = context.snapshot
        for contract in snapshot.contracts:
            # Reference criterion: candidate if last price > 0 and volume > 0
            if contract.last_price and contract.last_price > 0 and contract.volume and contract.volume > 0:
                reason = f"ACTIVE_OPTION_OBSERVED_{contract.option_type}"
                candidate = MarketCandidate(
                    scanner_id=self.scanner_id,
                    scanner_version=self.scanner_version,
                    market=contract.market,
                    exchange=contract.exchange,
                    asset_class="INDEX",
                    instrument_type=contract.instrument_type,
                    underlying=contract.underlying,
                    discovery_reason=reason,
                    snapshot_at=snapshot.timestamp,
                    canonical_contract_id=contract.canonical_contract_id,
                    expiry=contract.expiry,
                    strike=contract.strike,
                    option_type=contract.option_type,
                    evidence={
                        "last_price": Decimal(str(contract.last_price)),
                        "volume": contract.volume,
                        "open_interest": contract.open_interest,
                        "bid_price": contract.bid_price,  # Already Decimal from contract
                        "ask_price": contract.ask_price,    # Already Decimal from contract
                        "implied_volatility": Decimal(str(contract.implied_volatility)) if contract.implied_volatility else None,
                        "delta": Decimal(str(contract.delta)) if contract.delta is not None else None,
                    },
                    provider=contract.provider,
                )
                candidates.append(candidate)
        return candidates


class NiftyOptionsDiscoveryScanner:
    """First real NIFTY Options market discovery scanner.

    Performs market screening on normalized option-chain data to identify
    contracts worth sending forward for deeper analysis. Does NOT produce
    trade recommendations, execution instructions, or strategy signals.

    Screening dimensions (all independently configurable):
      A. expiry eligibility (nearest valid expiry from chain)
      B. strike proximity to ATM
      C. liquidity (volume/OI thresholds)
      D. bid/ask spread and tradability
      E. market-data quality

    The scanner treats CALL and PUT symmetrically — no bullish/bearish
    interpretation. CALL does NOT mean BUY; PUT does NOT mean SELL.

    Output: MarketCandidate instances for contracts passing screening.
    Data-quality failures are conceptually distinct from screening rejections
    for later observability purposes.
    """

    def __init__(
        self,
        scanner_id: str = "nifty-options-discovery",
        scanner_version: str = "1.0.0",
        # Expiry selection
        expiry_selection: str = "nearest",  # "nearest" or "explicit"
        # Strike proximity
        atm_proximity: int = 1,  # number of strike levels from ATM
        # Liquidity thresholds (development defaults, configurable)
        min_volume: int = 50,
        min_open_interest: int = 50,
        # Spread tolerance
        max_spread_pct: Decimal = Decimal("20.0"),  # 20% max spread
        # Data quality
        min_last_price: Decimal = Decimal("0.01"),
    ):
        self.scanner_id = scanner_id
        self.scanner_version = scanner_version
        self.expiry_selection = expiry_selection
        self.atm_proximity = atm_proximity
        self.min_volume = min_volume
        self.min_open_interest = min_open_interest
        self.max_spread_pct = max_spread_pct
        self.min_last_price = min_last_price

    def scan(self, context: ScannerContext) -> list[MarketCandidate]:
        """Screen normalized option-chain and emit MarketCandidates for eligible contracts."""
        candidates = []
        snapshot = context.snapshot
        spot = snapshot.spot_price

        # --- Expiry filter ---
        # Expiries come from the chain itself; we derive eligible set from available contracts
        all_contract_expiries = list({c.expiry for c in snapshot.contracts if c.expiry})
        eligible_expiries = self._filter_expiries(all_contract_expiries)
        if not eligible_expiries:
            return candidates

        # --- Screen contracts ---
        for contract in snapshot.contracts:
            # Data-quality gate (fail-fast, conceptually distinct from screening rejection)
            if not self._passes_data_quality(contract, spot):
                continue  # data-quality failure → later observability category

            # Expiry gate
            if contract.expiry not in eligible_expiries:
                continue

            # Strike proximity gate
            if not self._passes_strike_proximity(contract.strike, spot):
                continue

            # Liquidity gate
            if not self._passes_liquidity(contract):
                continue

            # Spread/tradability gate
            if not self._passes_spread(contract):
                continue

            # Build candidate (CALL and PUT symmetric — no bullish/bearish interpretation)
            evidence = self._build_evidence(contract, spot)

            candidate = MarketCandidate(
                scanner_id=self.scanner_id,
                scanner_version=self.scanner_version,
                market=contract.market,
                exchange=contract.exchange,
                asset_class="INDEX",
                instrument_type=contract.instrument_type,
                underlying=contract.underlying,
                discovery_reason=self._discovery_reason(contract),
                snapshot_at=snapshot.timestamp,
                canonical_contract_id=contract.canonical_contract_id,
                expiry=contract.expiry,
                strike=contract.strike,
                option_type=contract.option_type,
                evidence=evidence,
                provider=contract.provider,
            )
            candidates.append(candidate)

        return candidates

    # -------- internal gates --------

    def _filter_expiries(self, available_expiries: list[str] | None) -> list[str] | None:
        """Return the expiries this scanner considers eligible."""
        if not available_expiries:
            return None
        if self.expiry_selection == "nearest":
            # Return sorted by proximity to today; oldest first for index options
            try:
                from datetime import date
                today = date.today()
                sorted_expiries = sorted(available_expiries, key=lambda e: abs(
                    (date.fromisoformat(e) - today).days
                ))
                return [sorted_expiries[0]]  # single nearest
            except Exception:
                return available_expiries[:1]
        elif self.expiry_selection == "explicit":
            return available_expiries
        return None

    def _passes_data_quality(self, contract: NormalizedOptionContract, spot: Decimal) -> bool:
        """Data-quality gate. Fail-fast — conceptually distinct from screening rejection."""
        # Malformed prices
        if contract.last_price is None or contract.last_price <= 0:
            return False
        if contract.bid_price is not None and contract.bid_price <= 0:
            return False
        if contract.ask_price is not None and contract.ask_price <= 0:
            return False
        # Minimum last price
        if contract.last_price < self.min_last_price:
            return False
        # Zero/negative volume handling later in liquidity gate
        return True

    def _passes_strike_proximity(self, strike: Decimal, spot: Decimal) -> bool:
        """Contract must be within atm_proximity strike levels of ATM."""
        if strike is None or spot is None:
            return False
        # Determine ATM strike (closest to spot from available ladder)
        strike_diff = abs(Decimal(str(strike)) - spot)
        # We check if the strike is within the configured proximity
        # Since we don't have a full strike ladder here, we check relative distance
        # In a full implementation with the ladder, we'd rank all strikes.
        # For now: allow if within a reasonable band (1% of spot as development default,
        # but the configured atm_proximity modulates this).
        # The actual strike-ranking happens when the full ladder is present;
        # this method is a guard for the normalized-single-contract path.
        if strike_diff <= spot * Decimal("0.01") * Decimal(str(self.atm_proximity)):
            return True
        # Also allow ATM exactly
        if strike_diff == 0:
            return True
        return False

    def _passes_liquidity(self, contract: NormalizedOptionContract) -> bool:
        """Volume and open-interest thresholds."""
        if contract.volume is not None and contract.volume < self.min_volume:
            return False
        if contract.open_interest is not None and contract.open_interest < self.min_open_interest:
            return False
        return True

    def _passes_spread(self, contract: NormalizedOptionContract) -> bool:
        """Bid/ask spread check."""
        if contract.bid_price is None or contract.ask_price is None:
            return False  # missing prices → fail spread check
        if contract.ask_price <= contract.bid_price:
            return False  # ask must be >= bid
        spread_abs = abs(contract.ask_price - contract.bid_price)
        spread_pct = (spread_abs / contract.ask_price) * Decimal("100")
        if spread_pct > self.max_spread_pct:
            return False
        return True

    def _build_evidence(self, contract: NormalizedOptionContract, spot: Decimal) -> dict[str, Any]:
        """Build bounded evidence dict for the MarketCandidate."""
        spread_abs = abs(contract.ask_price - contract.bid_price) if contract.bid_price and contract.ask_price else Decimal("0")
        spread_pct = (spread_abs / contract.ask_price * Decimal("100")) if contract.ask_price else Decimal("0")
        strike_dec = Decimal(str(contract.strike)) if contract.strike else Decimal("0")
        return {
            "last_price": str(contract.last_price),
            "volume": contract.volume or 0,
            "open_interest": contract.open_interest or 0,
            "bid": str(contract.bid_price) if contract.bid_price else "0",
            "ask": str(contract.ask_price) if contract.ask_price else "0",
            "spread_absolute": str(spread_abs),
            "spread_percentage": str(spread_pct),
            "distance_from_spot": str(abs(strike_dec - spot)) if spot else "0",
            "expiry": contract.expiry or "",
            "option_type": contract.option_type or "",
        }

    def _discovery_reason(self, contract: NormalizedOptionContract) -> str:
        """Produce a clear, repository-consistent discovery reason string."""
        parts: list[str] = []
        if contract.expiry:
            parts.append(f"EXP{contract.expiry}")
        # strike proximity described by distance from spot
        if contract.strike is not None:
            try:
                s = Decimal(str(contract.strike))
                if s > 0:
                    parts.append(f"STRIKE@{contract.strike}")
            except Exception:
                pass
        parts.append(f"OTY{contract.option_type}")
        return "_".join(parts) if parts else "NIFTY_OPTION_SCREENED"
