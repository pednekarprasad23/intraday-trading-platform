"""Tests for versioned index-structure levels and order-block detection."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.market_data.structure import (
    BLOCK_WARMUP,
    SWING_LOOKBACK,
    VWAP_WARMUP,
    analyse,
    compute_vwap,
    detect_signals,
    order_blocks,
    prior_session_levels,
    swing_levels,
    to_dict,
)
from app.strategies.contracts import Candle


def _candle(
    offset_minutes: int,
    open: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    volume: Decimal = Decimal("1000"),
) -> Candle:
    base = datetime(2026, 11, 6, 9, 15, tzinfo=timezone.utc)
    return Candle(
        bar_time=base + timedelta(minutes=offset_minutes),
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


class TestPriorSessionLevels:
    def test_returns_high_and_low(self):
        formed = datetime(2026, 11, 5, 15, 30, tzinfo=timezone.utc)
        levels = prior_session_levels((), Decimal("100"), Decimal("90"), formed)
        assert len(levels) == 2
        kinds = {l.kind for l in levels}
        assert "prior_range_high" in kinds
        assert "prior_range_low" in kinds
        assert levels[0].provenance == "PRIOR_SESSION"


class TestVWAP:
    def test_none_with_insufficient_bars(self):
        bars = tuple(_candle(i, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100")) for i in range(VWAP_WARMUP - 1))
        assert compute_vwap(bars) is None

    def test_none_with_zero_volume(self):
        bars = tuple(_candle(i, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), Decimal("0")) for i in range(VWAP_WARMUP))
        assert compute_vwap(bars) is None

    def test_returns_level_with_sufficient_volume(self):
        bars = tuple(_candle(i, Decimal("100"), Decimal("102"), Decimal("98"), Decimal("101")) for i in range(VWAP_WARMUP))
        vwap = compute_vwap(bars)
        assert vwap is not None
        assert vwap.kind == "vwap"
        assert vwap.value.is_finite()


class TestSwingLevels:
    def test_empty_with_insufficient_bars(self):
        bars = tuple(_candle(i, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100")) for i in range(SWING_LOOKBACK * 2))
        assert swing_levels(bars) == ()

    def test_detects_swing_high(self):
        # Create a clear peak at index 5 with SWING_LOOKBACK=5, need 11 bars
        # bars[5] close=109, high=110; all others <=105 so pivot is strictly highest
        base_values = [
            Decimal("100"), Decimal("101"), Decimal("102"), Decimal("103"), Decimal("104"),
            Decimal("109"), Decimal("104"), Decimal("103"), Decimal("102"), Decimal("101"),
            Decimal("100"),
        ]
        bars = tuple(_candle(i, v, v + Decimal("1"), v - Decimal("1"), v) for i, v in enumerate(base_values))
        levels = swing_levels(bars)
        highs = [l for l in levels if l.kind == "swing_high"]
        assert len(highs) >= 1


class TestOrderBlocks:
    def test_empty_with_insufficient_bars(self):
        bars = tuple(_candle(i, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100")) for i in range(BLOCK_WARMUP))
        assert order_blocks(bars) == ()

    def test_detects_bull_block(self):
        # Need len(bars) >= BLOCK_WARMUP + 2 = 5
        # Add warmup bars so avg_body is meaningful
        bars = (
            _candle(0, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100")),  # small green
            _candle(1, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100")),  # flat
            _candle(2, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100")),  # flat
            _candle(3, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("99")),  # red
            _candle(4, Decimal("99"), Decimal("106"), Decimal("98"), Decimal("105")),  # strong green
        )
        blocks = order_blocks(bars)
        bulls = [b for b in blocks if b.kind == "bull"]
        assert len(bulls) >= 1


class TestDetectSignals:
    def test_empty_with_no_levels(self):
        bars = tuple(_candle(i, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100")) for i in range(5))
        assert detect_signals(bars, ()) == ()

    def test_breakout_above(self):
        from app.market_data.structure import PriceLevel
        level = PriceLevel("prior_range_high", Decimal("100"), datetime(2026, 11, 5, tzinfo=timezone.utc))
        bars = tuple(_candle(i, Decimal("99"), Decimal("101"), Decimal("98"), Decimal("101")) for i in range(5))
        signals = detect_signals(bars, (level,))
        breakouts = [s for s in signals if s.signal == "breakout_above"]
        assert len(breakouts) >= 1


class TestAnalyse:
    def test_returns_structure_result(self):
        bars = tuple(_candle(i, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100")) for i in range(20))
        result = analyse(bars, prior_high=Decimal("105"), prior_low=Decimal("95"))
        assert result is not None
        assert isinstance(result.levels, tuple)
        assert isinstance(result.warnings, tuple)

    def test_warning_without_prior_range(self):
        bars = tuple(_candle(i, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100")) for i in range(20))
        result = analyse(bars)
        assert any("prior-session" in w.lower() for w in result.warnings)

    def test_to_dict_roundtrip(self):
        bars = tuple(_candle(i, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100")) for i in range(20))
        result = analyse(bars, prior_high=Decimal("105"), prior_low=Decimal("95"))
        d = to_dict(result)
        assert d["version"] == 1
        assert "levels" in d
        assert "blocks" in d
        assert "signals" in d
        assert "warnings" in d


class TestValidation:
    def test_empty_bars_raises(self):
        with pytest.raises(ValueError, match="At least one bar"):
            analyse(())

    def test_missing_volume_raises(self):
        base = datetime(2026, 11, 6, 9, 15, tzinfo=timezone.utc)
        bar = Candle(
            bar_time=base,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=None,
        )
        with pytest.raises(ValueError, match="Volume is required"):
            analyse((bar,))
