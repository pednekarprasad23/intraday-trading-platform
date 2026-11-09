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
                        "last_price": str(contract.last_price),
                        "volume": contract.volume,
                        "open_interest": contract.open_interest,
                        "implied_volatility": str(contract.implied_volatility) if contract.implied_volatility else None,
                    },
                    provider=contract.provider,
                )
                candidates.append(candidate)
        return candidates
