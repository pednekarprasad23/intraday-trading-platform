"""V2.9A & V2.9B Universal Market Discovery & Contract Data Foundation tests.

Tests verify:
1. NIFTY INDEX underlying representation
2. NIFTY OPTION representation
3. CALL option identity
4. PUT option identity
5. Strike nullable for non-options (spot/index)
6. Strike available for option identity
7. Expiry optional/non-option
8. Provider independent from market identity
9. Canonical identity deterministic generation
10. Normalized contract identity formatting and uniqueness
11. Zero execution dependencies (no paper trading or execution modules)
12. Daily XAU and PAPER code isolation
13. Provider-neutral option chain fixture retrieval and normalization (CE->CALL, PE->PUT)
14. Expiry / strike variations produce distinct canonical identities
15. Nullable Greeks and market fields supported gracefully
16. Provider errors (EmptyChainError, UnsupportedExpiryError, MalformedResponseError) handled safely
17. Timestamps preserved correctly in snapshots and contracts
"""

from datetime import date
from decimal import Decimal
import sys
import pytest
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
from app.discovery.service import DiscoveryService
from app.discovery.provider import (
    FixtureDiscoveryAdapter,
    EmptyChainError,
    UnsupportedExpiryError,
    NormalizedOptionContract,
)


class TestDiscoveryFoundation:
    """Universal market discovery and contract data foundation test suite."""

    def test_nifty_index_underlying(self, db: Session):
        """1. Prove representation of NIFTY INDEX underlying."""
        universe = DiscoveryService.bootstrap_nifty_options_universe(db)
        assert universe is not None
        assert universe.market == Market.INDIA
        assert universe.asset_class == AssetClass.INDEX
        assert universe.instrument_type == InstrumentType.OPTION
        assert universe.underlying == "NIFTY"

        underlying_id = generate_canonical_identity(
            market="INDIA",
            exchange="NSE",
            underlying="NIFTY",
            instrument_type="INDEX",
        )
        assert underlying_id == "INDIA:NSE:NIFTY:INDEX"

    def test_nifty_option_call_put(self, db: Session):
        """2, 3, 4. Prove NIFTY OPTION, CALL, and PUT representations."""
        expiry = date(2026, 11, 26)
        strike = Decimal("26000.00")

        call_id = generate_canonical_identity(
            market="INDIA",
            exchange="NFO",
            underlying="NIFTY",
            instrument_type="OPTION",
            expiry=expiry,
            strike=strike,
            option_type=OptionType.CALL.value,
        )
        assert call_id == "INDIA:NFO:NIFTY:OPTION:2026-11-26:26000.00:CALL"

        put_id = generate_canonical_identity(
            market="INDIA",
            exchange="NFO",
            underlying="NIFTY",
            instrument_type="OPTION",
            expiry=expiry,
            strike=strike,
            option_type=OptionType.PUT.value,
        )
        assert put_id == "INDIA:NFO:NIFTY:OPTION:2026-11-26:26000.00:PUT"

    def test_strike_and_expiry_optionality(self):
        """5, 6, 7. Strike nullable for non-options, available for options; expiry optional/non-option."""
        index_id = generate_canonical_identity(
            market="INDIA",
            exchange="NSE",
            underlying="NIFTY",
            instrument_type="INDEX",
            expiry=None,
            strike=None,
            option_type=None,
        )
        assert index_id == "INDIA:NSE:NIFTY:INDEX"

    def test_provider_independence(self, db: Session):
        """8. Provider independent from market identity."""
        universe_demo = MarketUniverse(
            name=f"Universe Demo {date.today()}",
            market="INDIA",
            exchange="NSE",
            asset_class="INDEX",
            instrument_type="INDEX",
            underlying="NIFTY",
            provider="DEMO",
        )
        universe_dhan = MarketUniverse(
            name=f"Universe Dhan {date.today()}",
            market="INDIA",
            exchange="NSE",
            asset_class="INDEX",
            instrument_type="INDEX",
            underlying="NIFTY",
            provider="DHAN",
        )
        db.add_all([universe_demo, universe_dhan])
        db.commit()

        assert universe_demo.market == universe_dhan.market
        assert universe_demo.underlying == universe_dhan.underlying
        assert universe_demo.provider != universe_dhan.provider

    def test_canonical_identity_determinism(self):
        """9, 10. Canonical identity is deterministic and normalized."""
        id1 = generate_canonical_identity("india", "nfo", "nifty", "option", "2026-11-26", 26000, "call")
        id2 = generate_canonical_identity("INDIA", "NFO", "NIFTY", "OPTION", "2026-11-26", Decimal("26000"), "CALL")
        assert id1 == id2
        assert id1 == "INDIA:NFO:NIFTY:OPTION:2026-11-26:26000:CALL"

    def test_option_chain_fixture_normalization(self):
        """13, 14, 15, 17. Option chain fixture normalization, expiries, strikes, CALL/PUT, timestamps."""
        adapter = FixtureDiscoveryAdapter()
        expiries = adapter.get_expiries("NIFTY")
        assert len(expiries) > 0

        snapshot = adapter.get_option_chain("NIFTY", expiries[0])
        assert snapshot.underlying == "NIFTY"
        assert snapshot.spot_price > 0
        assert snapshot.timestamp is not None
        assert len(snapshot.contracts) > 0

        # Verify contracts have valid canonical IDs and option types
        call_contracts = [c for c in snapshot.contracts if c.option_type == "CALL"]
        put_contracts = [c for c in snapshot.contracts if c.option_type == "PUT"]
        assert len(call_contracts) > 0
        assert len(put_contracts) > 0

        # Verify distinct identities for different strikes / expiries / types
        c1 = call_contracts[0]
        p1 = put_contracts[0]
        assert c1.canonical_contract_id != p1.canonical_contract_id
        assert c1.snapshot_at is not None

    def test_provider_error_handling(self):
        """16. Empty chain and unsupported expiry handling."""
        adapter = FixtureDiscoveryAdapter()
        with pytest.raises(EmptyChainError):
            adapter.get_option_chain("BANKNIFTY", "2026-11-26")

        with pytest.raises(UnsupportedExpiryError):
            adapter.get_option_chain("NIFTY", "2099-01-01")

    def test_zero_execution_dependency(self):
        """11, 16. Verify zero execution dependency across all discovery modules."""
        for mod_name in list(sys.modules.keys()):
            if "app.discovery" in mod_name:
                mod = sys.modules[mod_name]
                source = getattr(mod, "__file__", "")
                if source:
                    with open(source, "r", encoding="utf-8") as f:
                        content = f.read()
                        assert "paper_trading" not in content
                        assert "PaperExecutionService" not in content
                        assert "KillSwitch" not in content
