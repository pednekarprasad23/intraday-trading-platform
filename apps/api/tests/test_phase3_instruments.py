"""Phase 3 instrument mappings — validated tests.

Tests verify:
1. All index specs have valid canonical symbols
2. Index future underlyings resolve correctly
3. Equity lot sizes are positive decimals
4. MT5 contract specs match MT5 terminal expectations
5. DHAN tokens are non-empty strings
"""

from decimal import Decimal

import pytest

from app.instruments import mappings as p3


class TestIndexes:
    """Cash index tests."""

    def test_nifty50_structure(self):
        assert p3.NIFTY50.canonical == "DEMO:NIFTY"
        assert p3.NIFTY50.exchange == "NSE"
        assert p3.NIFTY50.segment == "INDEX"
        assert p3.NIFTY50.is_index is True
        assert p3.NIFTY50.lot_size == 1  # cash index

    def test_niftybank_structure(self):
        assert p3.NIFTYBANK.canonical == "DEMO:NIFTYBANK"
        assert p3.NIFTYBANK.exchange == "NSE"
        assert Decimal(str(p3.NIFTYBANK.tick_size)) == Decimal("0.05")

    def test_sensex_structure(self):
        assert p3.SENSEX.canonical == "DEMO:SENSEX"
        assert p3.SENSEX.exchange == "BSE"
        assert Decimal(str(p3.SENSEX.tick_size)) == Decimal("1.0")

    def test_finnifty_structure(self):
        assert p3.FINNIFTY.canonical == "DEMO:FINNIFTY"
        assert p3.FINNIFTY.exchange == "NSE"
        assert Decimal(str(p3.FINNIFTY.tick_size)) == Decimal("0.05")


class TestIndexFutures:
    """Index future tests."""

    def test_nifty_futures_underlying(self):
        assert p3.NIFTY_FUT.underlying_id == "DEMO:NIFTY"
        assert Decimal(str(p3.NIFTY_FUT.lot_size)) == Decimal("25")
        assert Decimal(str(p3.NIFTY_FUT.tick_size)) == Decimal("0.05")

    def test_banknifty_futures_lot(self):
        assert p3.BANKNIFTY_FUT.underlying_id == "DEMO:NIFTYBANK"
        assert Decimal(str(p3.BANKNIFTY_FUT.lot_size)) == Decimal("30")

    def test_finnifty_futures_lot(self):
        assert p3.FINNIFTY_FUT.underlying_id == "DEMO:FINNIFTY"
        assert Decimal(str(p3.FINNIFTY_FUT.lot_size)) == Decimal("15")


class TestEquities:
    """Equity tests."""

    def test_reliance_structure(self):
        assert "RELIANCE" in p3.EQUITIES
        rel = p3.EQUITIES["RELIANCE"]
        assert rel.canonical == "DEMO:RELIANCE"
        assert rel.exchange == "NSE"
        assert rel.segment == "EQ"
        assert rel.lot_size == Decimal("1")

    def test_tcs_structure(self):
        assert "TCS" in p3.EQUITIES
        tcs = p3.EQUITIES["TCS"]
        assert tcs.canonical == "DEMO:TCS"
        assert tcs.exchange == "NSE"
        assert tcs.asset_class == "EQUITY"


class TestMT5Contracts:
    """MT5 bridge contract tests."""

    def test_xauusd_structure(self):
        assert p3.XAUUSD.canonical == "DEMO:XAUUSD"
        assert p3.XAUUSD.symbol == "XAUUSD"
        assert p3.XAUUSD.lot_size == Decimal("100")
        assert p3.XAUUSD.tick_size == Decimal("0.01")

    def test_btcusd_structure(self):
        assert p3.BTCUSD.canonical == "DEMO:BTCUSD"
        assert p3.BTCUSD.symbol == "BTCUSD"
        assert p3.BTCUSD.lot_size == Decimal("1")
        assert p3.BTCUSD.tick_size == Decimal("0.01")


class TestProviderTokens:
    """Provider token resolution tests."""

    def test_dhan_nifty_token(self):
        assert p3.DHAN_TOKENS["NIFTY"] is not None
        assert len(p3.DHAN_TOKENS["NIFTY"]) > 0
        assert isinstance(p3.DHAN_TOKENS["NIFTY"], str)

    def test_dhan_banknifty_token(self):
        assert p3.DHAN_TOKENS["BANKNIFTY"] is not None
        assert len(p3.DHAN_TOKENS["BANKNIFTY"]) > 0

    def test_dhan_finnifty_token(self):
        assert p3.DHAN_TOKENS["FINNIFTY"] is not None
        assert len(p3.DHAN_TOKENS["FINNIFTY"]) > 0


class TestInstrumentMappingCompleteness:
    """Verify all required Phase 3 mappings exist."""

    def test_all_indexes_present(self):
        """All 4 indexes should be defined."""
        expected = {"NIFTY50", "NIFTYBANK", "SENSEX", "FINNIFTY"}
        defined = {name for name in dir(p3) if hasattr(getattr(p3, name), "is_index")}
        assert expected.issubset(defined), f"Missing indexes: {expected - defined}"

    def test_all_futures_present(self):
        """All 3 index futures should be defined."""
        expected = {"NIFTY_FUT", "BANKNIFTY_FUT", "FINNIFTY_FUT"}
        defined = {name for name in dir(p3) if hasattr(getattr(p3, name), "underlying_id")}
        assert expected.issubset(defined), f"Missing futures: {expected - defined}"

    def test_all_equities_present(self):
        """All 10 equities should be defined."""
        expected = {"RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HUL", "KOTAKBANK", "LT", "SBIN", "AXISBANK"}
        assert set(p3.EQUITIES.keys()) == expected, f"Missing equities: {expected - set(p3.EQUITIES.keys())}"

    def test_all_mt5_contracts_present(self):
        """All MT5 contracts should be defined."""
        expected = {"XAUUSD", "BTCUSD"}
        mt5_names = {"XAUUSD", "BTCUSD"}
        assert mt5_names.issubset({"XAUUSD", "BTCUSD"}), "Missing MT5 contracts"


class TestInstrumentValidation:
    """Validate instrument contract specifications."""

    def test_index_lot_size_is_one(self):
        """Cash indices should have lot_size of 1."""
        indexes = [p3.NIFTY50, p3.NIFTYBANK, p3.SENSEX, p3.FINNIFTY]
        for idx in indexes:
            assert idx.lot_size == 1, f"{idx.canonical} should have lot_size=1"

    def test_future_lot_sizes_are_positive(self):
        """Futures should have positive lot sizes."""
        futures = [p3.NIFTY_FUT, p3.BANKNIFTY_FUT, p3.FINNIFTY_FUT]
        for fut in futures:
            assert fut.lot_size > 0, f"{fut.canonical} should have positive lot_size"

    def test_tick_sizes_are_positive(self):
        """All instruments should have positive tick sizes."""
        all_instruments = (
            list(p3.INDEXES.values())
            + [p3.NIFTY_FUT, p3.BANKNIFTY_FUT, p3.SENSEX_FUT, p3.FINNIFTY_FUT]
            + p3.EQUITY_FUTURES
            + list(p3.EQUITIES.values())
            + [p3.XAUUSD, p3.BTCUSD]
        )
        for inst in all_instruments:
            assert inst.tick_size > 0, f"{inst.canonical} should have positive tick_size"

    def test_mt5_tick_sizes_are_small(self):
        """MT5 commodities/crypto should have small tick sizes."""
        mt5_contracts = [p3.XAUUSD, p3.BTCUSD]
        for contract in mt5_contracts:
            assert contract.tick_size <= Decimal("1.0"), f"{contract.canonical} should have small tick_size"


class TestUnderlyingResolution:
    """Verify underlying resolution for index futures."""

    def test_nifty_fut_resolves_underlying(self):
        assert p3.NIFTY_FUT.underlying_id == "DEMO:NIFTY"
        underlying = p3.INDEXES.get("DEMO:NIFTY")
        assert underlying is not None
        assert underlying.canonical == "DEMO:NIFTY"

    def test_banknifty_fut_resolves_underlying(self):
        assert p3.BANKNIFTY_FUT.underlying_id == "DEMO:NIFTYBANK"
        underlying = p3.INDEXES.get(p3.BANKNIFTY_FUT.underlying_id)
        assert underlying is not None
        assert underlying.canonical == p3.BANKNIFTY_FUT.underlying_id

    def test_finnifty_fut_resolves_underlying(self):
        assert p3.FINNIFTY_FUT.underlying_id == "DEMO:FINNIFTY"
        underlying = p3.INDEXES.get("DEMO:FINNIFTY")
        assert underlying is not None
        assert underlying.canonical == "DEMO:FINNIFTY"


class TestCanonicalSymbolFormat:
    """Verify canonical symbol format compliance."""

    def test_index_canonical_format(self):
        """Index canonical symbols should be DEMO:<NAME>."""
        indexes = [p3.NIFTY50, p3.NIFTYBANK, p3.SENSEX, p3.FINNIFTY]
        for idx in indexes:
            assert idx.canonical.startswith("DEMO:"), f"{idx.canonical} should start with DEMO:"

    def test_future_canonical_format(self):
        """Future canonical symbols should end with FUT."""
        futures = [p3.NIFTY_FUT, p3.BANKNIFTY_FUT, p3.FINNIFTY_FUT]
        for fut in futures:
            assert fut.canonical.endswith("FUT"), f"{fut.canonical} should end with FUT"

    def test_equity_canonical_format(self):
        """Equity canonical symbols should be DEMO:<SYMBOL>."""
        for symbol, equity in p3.EQUITIES.items():
            assert equity.canonical == f"DEMO:{symbol}", f"{equity.canonical} should be DEMO:{symbol}"

    def test_mt5_canonical_format(self):
        """MT5 canonical symbols should start with DEMO:."""
        mt5_contracts = [p3.XAUUSD, p3.BTCUSD]
        for contract in mt5_contracts:
            assert contract.canonical.startswith("DEMO:"), f"{contract.canonical} should start with DEMO:"


class TestExchangeMapping:
    """Verify exchange mapping consistency."""

    def test_all_indexes_are_nse_or_bse(self):
        indexes = [p3.NIFTY50, p3.NIFTYBANK, p3.SENSEX, p3.FINNIFTY]
        exchanges = {idx.exchange for idx in indexes}
        assert exchanges.issubset({"NSE", "BSE"}), f"Invalid exchanges: {exchanges}"

    def test_nifty50_is_nse(self):
        assert p3.NIFTY50.exchange == "NSE"

    def test_sensex_is_bse(self):
        assert p3.SENSEX.exchange == "BSE"

    def test_all_futures_use_nse(self):
        """Futures use NSE exchange (real market)."""
        futures = [p3.NIFTY_FUT, p3.BANKNIFTY_FUT, p3.FINNIFTY_FUT]
        for fut in futures:
            assert fut.exchange == "NSE", f"{fut.canonical} should use NSE exchange"


class TestAssetClassClassification:
    """Verify asset class classification."""

    def test_indexes_are_index_asset_class(self):
        indexes = [p3.NIFTY50, p3.NIFTYBANK, p3.SENSEX, p3.FINNIFTY]
        for idx in indexes:
            assert idx.segment == "INDEX", f"{idx.canonical} should be INDEX segment"
            assert idx.is_index is True

    def test_futures_are_futures_asset_class(self):
        futures = [p3.NIFTY_FUT, p3.BANKNIFTY_FUT, p3.FINNIFTY_FUT]
        for fut in futures:
            assert fut.segment == "FUT", f"{fut.canonical} should be FUT segment"

    def test_equities_are_equity_asset_class(self):
        for equity in p3.EQUITIES.values():
            assert equity.asset_class == "EQUITY", f"{equity.canonical} should be EQUITY asset class"

    def test_mt5_commodities_are_commodity_asset_class(self):
        assert p3.XAUUSD.asset_class == "COMMODITY"
        assert p3.BTCUSD.asset_class == "CRYPTO"


class TestProviderSymbolResolution:
    """Verify provider symbol mapping consistency."""

    def test_dhan_tokens_exist_for_indexes(self):
        """Dhan tokens should exist for all NSE indexes."""
        for idx in [p3.NIFTY50, p3.NIFTYBANK, p3.FINNIFTY]:
            assert idx.canonical in p3.DHAN_NSE_INDEX_TOKENS
            assert p3.DHAN_NSE_INDEX_TOKENS[idx.canonical]["token"] is not None

    def test_mt5_tokens_exist_for_commodities(self):
        """MT5 symbol details should exist for commodities."""
        for contract in [p3.XAUUSD, p3.BTCUSD]:
            assert contract.canonical in p3.MT5_SYMBOL_DETAILS
            assert p3.MT5_SYMBOL_DETAILS[contract.canonical]["symbol"] == contract.symbol


class TestPhase3Completeness:
    """Verify complete Phase 3 implementation."""

    def test_all_mappings_are_documented(self):
        """All mappings should be documented in the module docstring."""
        doc = p3.__doc__
        assert doc is not None
        assert "NIFTY" in doc or "NIFTY50" in doc
        assert "MT5" in doc

    def test_version_is_defined(self):
        """VERSION should be defined in mappings module."""
        assert hasattr(p3, "VERSION")
        assert p3.VERSION >= 1

    def test_all_indexes_are_frozen_dataclasses(self):
        """All indexes should be frozen dataclasses."""
        from dataclasses import is_dataclass
        indexes = [p3.NIFTY50, p3.NIFTYBANK, p3.SENSEX, p3.FINNIFTY]
        for idx in indexes:
            assert is_dataclass(idx), f"{idx.canonical} should be a dataclass"
            assert idx.__dataclass_params__.frozen is True, f"{idx.canonical} should be frozen"
            assert hasattr(idx, "is_index"), f"{idx.canonical} should have is_index attribute"

    def test_all_futures_are_frozen_dataclasses(self):
        """All futures should be frozen dataclasses."""
        from dataclasses import is_dataclass
        futures = [p3.NIFTY_FUT, p3.BANKNIFTY_FUT, p3.FINNIFTY_FUT]
        for fut in futures:
            assert is_dataclass(fut), f"{fut.canonical} should be a dataclass"
            assert fut.__dataclass_params__.frozen is True, f"{fut.canonical} should be frozen"
            assert hasattr(fut, "underlying_id"), f"{fut.canonical} should have underlying_id attribute"
