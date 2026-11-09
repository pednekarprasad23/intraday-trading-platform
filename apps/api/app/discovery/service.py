"""Discovery service for bootstrapping market universes and validating canonical identities.

Strictly decoupled from execution and trading modules.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.discovery.models import (
    AssetClass,
    Exchange,
    InstrumentType,
    Market,
    MarketUniverse,
    OptionType,
    generate_canonical_identity,
)


class DiscoveryService:
    """Service managing discovery universes and normalized market identities."""

    @staticmethod
    def bootstrap_nifty_options_universe(db: Session) -> MarketUniverse:
        """Bootstrap the NIFTY Options V1 universe (initial configured discovery scope)."""
        universe_name = "NIFTY Options V1"
        existing = db.scalar(select(MarketUniverse).where(MarketUniverse.name == universe_name))
        if existing:
            return existing

        universe = MarketUniverse(
            name=universe_name,
            market=Market.INDIA,
            exchange=Exchange.NFO,
            asset_class=AssetClass.INDEX,
            instrument_type=InstrumentType.OPTION,
            sector="INDEX",
            underlying="NIFTY",
            provider="DEMO",
            enabled=True,
            universe_metadata={
                "description": "NIFTY Index Options V1 Discovery Universe",
                "option_types": [OptionType.CALL.value, OptionType.PUT.value],
                "timeframes": ["1m", "3m", "5m", "15m", "1h", "1d"],
            },
        )
        db.add(universe)
        db.commit()
        db.refresh(universe)
        return universe

    @staticmethod
    def build_contract_identity(
        market: str,
        exchange: str,
        underlying: str,
        instrument_type: str,
        expiry: Any | None = None,
        strike: Any | None = None,
        option_type: str | None = None,
    ) -> str:
        """Build a normalized canonical contract identity."""
        return generate_canonical_identity(
            market=market,
            exchange=exchange,
            underlying=underlying,
            instrument_type=instrument_type,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
        )
