"""Versioned index-structure levels and order-block candidates.

Rules are **versioned** so definitions can evolve without silently
altering past reports.  Every computation uses only *completed* bars
and explicitly records formation, invalidation and counter-evidence.
No live feed or look-ahead is assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from app.strategies.contracts import Candle

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

LevelKind = Literal["prior_range_high", "prior_range_low", "vwap",
                     "swing_high", "swing_low", "order_block_bull",
                     "order_block_bear", "intraday_high", "intraday_low"]
SignalKind = Literal["breakout_above", "breakout_below", "retest_bull",
                     "retest_bear", "none"]


@dataclass(frozen=True)
class DecimalRange:
    low: Decimal
    high: Decimal


@dataclass(frozen=True)
class PriceLevel:
    kind: LevelKind
    value: Decimal
    formed_at: datetime  # UTC when first observable (bar close)
    provenance: str = "HISTORICAL"


@dataclass(frozen=True)
class OrderBlock:
    kind: Literal["bull", "bear"]
    body_open: Decimal
    body_close: Decimal
    range_: DecimalRange = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "range_", DecimalRange(
            low=min(self.body_open, self.body_close),
            high=max(self.body_open, self.body_close),
        ))


@dataclass(frozen=True)
class BreakoutSignal:
    bar_time: datetime
    signal: SignalKind
    level: PriceLevel
    counter_evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StructureResult:
    levels: tuple[PriceLevel, ...] = ()
    blocks: tuple[OrderBlock, ...] = ()
    signals: tuple[BreakoutSignal, ...] = ()
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Versioned configuration
# ---------------------------------------------------------------------------

VERSION = 1

SWING_LOOKBACK = 5  # bars on each side for swing detection
VWAP_WARMUP = 10  # minimum bars before VWAP is valid
BLOCK_WARMUP = 3  # minimum bars before first block is observable


def _validate_bars(bars: tuple[Candle, ...]) -> None:
    if not bars:
        raise ValueError("At least one bar is required")
    for bar in bars:
        if bar.volume is None:
            raise ValueError("Volume is required for structure analysis")


# ---------------------------------------------------------------------------
# Core computations
# ---------------------------------------------------------------------------

def prior_session_levels(
    bars: tuple[Candle, ...],
    prior_high: Decimal,
    prior_low: Decimal,
    formed_at: datetime,
) -> tuple[PriceLevel, ...]:
    """Prior-session high / low — observable before the current session opens."""
    return (
        PriceLevel("prior_range_high", prior_high, formed_at, "PRIOR_SESSION"),
        PriceLevel("prior_range_low", prior_low, formed_at, "PRIOR_SESSION"),
    )


def compute_vwap(
    bars: tuple[Candle, ...],
) -> PriceLevel | None:
    """Session VWAP from completed bars; None if warm-up not met."""
    if len(bars) < VWAP_WARMUP:
        return None
    total_vol = Decimal(0)
    cum_typ = Decimal(0)
    for bar in bars:
        typical = (bar.high + bar.low + bar.close) / Decimal(3)
        cum_typ += typical * bar.volume
        total_vol += bar.volume
    if total_vol == Decimal(0):
        return None
    return PriceLevel(
        "vwap",
        cum_typ / total_vol,
        bars[-1].bar_time,
        "SESSION_COMPUTED",
    )


def swing_levels(
    bars: tuple[Candle, ...],
) -> tuple[PriceLevel, ...]:
    """Swing highs / lows with symmetric lookback; only completed bars."""
    if len(bars) < SWING_LOOKBACK * 2 + 1:
        return ()
    levels: list[PriceLevel] = []
    for i in range(SWING_LOOKBACK, len(bars) - SWING_LOOKBACK):
        pivot = bars[i]
        left = bars[i - SWING_LOOKBACK: i]
        right = bars[i + 1: i + SWING_LOOKBACK + 1]
        if all(p.high < pivot.high for p in left + right):
            levels.append(PriceLevel("swing_high", pivot.high, pivot.bar_time))
        if all(p.low > pivot.low for p in left + right):
            levels.append(PriceLevel("swing_low", pivot.low, pivot.bar_time))
    return tuple(levels)


def order_blocks(
    bars: tuple[Candle, ...],
) -> tuple[OrderBlock, ...]:
    """Versioned order-block detection.

    Bull block: last red bar before a strong green move (body >= 1.5x
    preceding average body).  Bear block: last green bar before a
    strong red move.  Requires ``BLOCK_WARMUP`` bars before the first
    observable block.
    """
    if len(bars) < BLOCK_WARMUP + 2:
        return ()
    blocks: list[OrderBlock] = []
    bodies = []
    for bar in bars:
        bodies.append(abs(bar.close - bar.open))
    for i in range(len(bars) - 1):
        curr = bars[i]
        nxt = bars[i + 1]
        avg_body = sum(bodies[:max(i, 1)]) / max(i, 1)
        curr_body = abs(curr.close - curr.open)
        if curr_body <= Decimal(0):
            continue
        # Bull block: red bar followed by strong green
        if (curr.close < curr.open
                and nxt.close > nxt.open
                and nxt.close - nxt.open >= Decimal("1.5") * avg_body):
            blocks.append(OrderBlock("bull", curr.open, curr.close))
        # Bear block: green bar followed by strong red
        elif (curr.close > curr.open
              and nxt.close < nxt.open
              and curr.close - curr.open >= Decimal("1.5") * avg_body):
            blocks.append(OrderBlock("bear", curr.open, curr.close))
    return tuple(blocks)


def intraday_levels(
    bars: tuple[Candle, ...],
) -> tuple[PriceLevel, ...]:
    """Intraday high / low — updated as each bar closes."""
    if not bars:
        return ()
    high = max(bar.high for bar in bars)
    low = min(bar.low for bar in bars)
    return (
        PriceLevel("intraday_high", high, bars[-1].bar_time),
        PriceLevel("intraday_low", low, bars[-1].bar_time),
    )


# ---------------------------------------------------------------------------
# Breakout / retest signals
# ---------------------------------------------------------------------------

def detect_signals(
    bars: tuple[Candle, ...],
    levels: tuple[PriceLevel, ...],
) -> tuple[BreakoutSignal, ...]:
    """Detect breakout / retest signals using only completed bars.

    A breakout fires when a bar *closes* beyond a level (not just wicks).
    A retest fires when price touches a breakout level and closes back
    inside the level range.
    """
    if not bars or not levels:
        return ()
    signals: list[BreakoutSignal] = []
    # Build lookup: kind -> value
    level_map: dict[LevelKind, PriceLevel] = {}
    for lvl in levels:
        level_map[lvl.kind] = lvl

    # Track breakout state per level
    broken_above: set[LevelKind] = set()
    broken_below: set[LevelKind] = set()

    for i, bar in enumerate(bars):
        for lvl in levels:
            if lvl.kind in ("prior_range_high", "prior_range_low",
                            "intraday_high", "intraday_low",
                            "swing_high", "swing_low",
                            "vwap"):
                if lvl.kind in broken_above:
                    # Check retest
                    if bar.close >= lvl.value and bar.close <= lvl.value + lvl.value * Decimal("0.005"):
                        signals.append(BreakoutSignal(
                            bar.bar_time, "retest_bull", lvl,
                            ["Price returned to broken-high level"],
                        ))
                    continue
                if lvl.kind in broken_below:
                    if bar.close <= lvl.value and bar.close >= lvl.value - lvl.value * Decimal("0.005"):
                        signals.append(BreakoutSignal(
                            bar.bar_time, "retest_bear", lvl,
                            ["Price returned to broken-low level"],
                        ))
                    continue
                # Check breakout
                if lvl.kind in ("prior_range_high", "intraday_high", "swing_high"):
                    if bar.close > lvl.value:
                        broken_above.add(lvl.kind)
                        signals.append(BreakoutSignal(
                            bar.bar_time, "breakout_above", lvl,
                            ["Close above resistance level"],
                        ))
                elif lvl.kind in ("prior_range_low", "intraday_low", "swing_low"):
                    if bar.close < lvl.value:
                        broken_below.add(lvl.kind)
                        signals.append(BreakoutSignal(
                            bar.bar_time, "breakout_below", lvl,
                            ["Close below support level"],
                        ))

    return tuple(signals)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyse(
    bars: tuple[Candle, ...],
    prior_high: Decimal | None = None,
    prior_low: Decimal | None = None,
    prior_formed_at: datetime | None = None,
) -> StructureResult:
    """Versioned index-structure analysis.

    All inputs are completed bars.  No look-ahead.
    """
    _validate_bars(bars)
    warnings: list[str] = []
    levels: list[PriceLevel] = []
    blocks: list[OrderBlock] = []
    signals: list[BreakoutSignal] = []

    # Prior session levels
    if prior_high is not None and prior_low is not None:
        formed = prior_formed_at or bars[-1].bar_time
        levels.extend(prior_session_levels(bars, prior_high, prior_low, formed))
    else:
        warnings.append("No prior-session range provided; breakout detection limited")

    # Intraday levels
    levels.extend(intraday_levels(bars))

    # VWAP
    vwap = compute_vwap(bars)
    if vwap:
        levels.append(vwap)
    else:
        warnings.append("VWAP undefined: insufficient bars or zero volume")

    # Swing levels
    levels.extend(swing_levels(bars))

    # Order blocks
    blocks = order_blocks(bars)

    # Signals
    signals = detect_signals(bars, tuple(levels))

    return StructureResult(
        levels=tuple(levels),
        blocks=tuple(blocks),
        signals=tuple(signals),
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# API response projection
# ---------------------------------------------------------------------------

def to_dict(result: StructureResult) -> dict:
    return {
        "version": VERSION,
        "levels": [
            {
                "kind": l.kind,
                "value": str(l.value),
                "formed_at": l.formed_at.isoformat(),
                "provenance": l.provenance,
            }
            for l in result.levels
        ],
        "blocks": [
            {
                "kind": b.kind,
                "body_open": str(b.body_open),
                "body_close": str(b.body_close),
                "range_low": str(b.range_.low),
                "range_high": str(b.range_.high),
            }
            for b in result.blocks
        ],
        "signals": [
            {
                "bar_time": s.bar_time.isoformat(),
                "signal": s.signal,
                "level_kind": s.level.kind,
                "level_value": str(s.level.value),
                "counter_evidence": s.counter_evidence,
            }
            for s in result.signals
        ],
        "warnings": list(result.warnings),
    }
