"""Validated, idempotent offline instrument metadata import."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Instrument, ProviderSymbol


@dataclass(frozen=True)
class MasterEntry:
    canonical_symbol: str
    display_name: str
    asset_class: str
    exchange: str
    segment: str
    provider: str
    provider_key: str
    provider_exchange: str
    expiry_date: date | None = None
    strike_price: Decimal | None = None
    option_type: str | None = None
    verified_at: datetime | None = None
    is_demo: bool = True

    def __post_init__(self):
        if not self.canonical_symbol or not self.provider_key:
            raise ValueError("Instrument and provider identities are required")
        if self.verified_at is not None and (
            self.verified_at.tzinfo is None or self.verified_at.utcoffset() is None
        ):
            raise ValueError("Verification time must be timezone-aware")
        if self.asset_class == "OPTION" and (
            self.expiry_date is None
            or self.strike_price is None
            or self.option_type not in {"CE", "PE"}
        ):
            raise ValueError("Options require verified expiry, strike and option type")
        if self.strike_price is not None and self.strike_price <= 0:
            raise ValueError("Strike must be positive")
        if not self.is_demo and self.verified_at is None:
            raise ValueError("Non-demo metadata requires source verification time")


def import_master(db: Session, entries: list[MasterEntry]) -> dict[str, int]:
    """Transactional import; never activates execution or silently changes identity."""
    seen_symbols: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    for entry in entries:
        identity = (entry.provider, entry.provider_key)
        if entry.canonical_symbol in seen_symbols or identity in seen_keys:
            raise ValueError("Duplicate identity in import batch")
        seen_symbols.add(entry.canonical_symbol)
        seen_keys.add(identity)
    created = 0
    updated = 0
    with db.begin_nested():
        for entry in entries:
            instrument = db.scalar(
                select(Instrument).where(
                    Instrument.canonical_symbol == entry.canonical_symbol
                )
            )
            mapping = db.scalar(
                select(ProviderSymbol).where(
                    ProviderSymbol.provider == entry.provider,
                    ProviderSymbol.provider_instrument_key == entry.provider_key,
                )
            )
            if mapping and (
                instrument is None or mapping.instrument_id != instrument.id
            ):
                raise ValueError("Provider token collision: cannot silently remap")
            if instrument and instrument.is_demo != entry.is_demo:
                raise ValueError("Demo identity cannot silently become verified")
            if not instrument:
                instrument = Instrument(
                    canonical_symbol=entry.canonical_symbol,
                    display_name=entry.display_name,
                    asset_class=entry.asset_class,
                    exchange=entry.exchange,
                    segment=entry.segment,
                    is_demo=entry.is_demo,
                )
                db.add(instrument)
                db.flush()
                created += 1
            else:
                updated += 1
                instrument.display_name = entry.display_name
            instrument.expiry_date = entry.expiry_date
            instrument.strike_price = entry.strike_price
            instrument.option_type = entry.option_type
            instrument.metadata_source = (
                entry.provider if not entry.is_demo else "DEMO_FIXTURE"
            )
            if not mapping:
                if db.scalar(
                    select(ProviderSymbol).where(
                        ProviderSymbol.instrument_id == instrument.id,
                        ProviderSymbol.provider == entry.provider,
                    )
                ):
                    raise ValueError(
                        "Existing mapping requires explicit rotation review"
                    )
                mapping = ProviderSymbol(
                    instrument_id=instrument.id,
                    provider=entry.provider,
                    provider_instrument_key=entry.provider_key,
                )
                db.add(mapping)
            mapping.provider_exchange = entry.provider_exchange
            mapping.last_verified_at = entry.verified_at
            mapping.data_enabled = (
                False  # Entitlement must be independently established.
            )
            mapping.execution_enabled = False
        db.flush()
    return {"created": created, "updated": updated}
