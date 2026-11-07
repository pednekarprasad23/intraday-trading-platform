"""Market regime detection and CE/PE regime-aware sampling.

Regimes are classified by realized volatility of the underlying over a
lookback window.  The caller supplies closing prices and a lookback
period; the module returns a regime label that the backtest harness
uses to pick the right cost envelope.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal as D

from app.backtesting.costs import CostEnvelope, Regime, REGIME_MULTIPLIERS
from app.strategies.contracts import Candle


@dataclass(frozen=True)
class RegimeInfo:
    """Metadata about a detected market regime for one session."""

    regime: Regime
    realized_vol: D  # annualized volatility as a fraction, e.g. 0.15 = 15%
    lookback_bars: int
    session_date: date
    cost_envelope: CostEnvelope


# Volatility thresholds (annualized, as a fraction)
_LOW_VOL_CEILING = D("0.10")
_HIGH_VOL_CEILING = D("0.25")
_CRISIS_CEILING = D("1.0")  # effectively open-ended


def _mean(values):
    if not values:
        return D(0)
    return sum(values) / len(values)


def _std(values):
    if len(values) < 2:
        return D(0)
    m = _mean(values)
    variance = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    # Newton's method square root for Decimal
    if variance <= 0:
        return D(0)
    x = D(str(float(variance) ** 0.5))
    for _ in range(50):
        x = (x + variance / x) / 2
    return x


def classify_regime(realized_vol: D) -> Regime:
    """Map an annualized realized volatility to a regime label.

    Thresholds:
        0 – 10%   → low_vol
        10% – 25% → normal
        25% – 100% → high_vol
        > 100%    → crisis
    """
    if realized_vol <= _LOW_VOL_CEILING:
        return "low_vol"
    if realized_vol <= _HIGH_VOL_CEILING:
        return "normal"
    if realized_vol <= _CRISIS_CEILING:
        return "high_vol"
    return "crisis"


def realized_volatility(closes, trading_days_per_year: int = 252) -> D:
    """Compute annualized realized volatility from a sequence of Decimal closes.

    Uses log returns over consecutive bars and scales by sqrt(trading_days).
    Each bar is assumed to represent 1 trading day for annualization.
    For intraday bars the caller should pass an adjusted trading_days_per_year.
    """
    if len(closes) < 2:
        return D(0)
    log_returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            log_returns.append((closes[i] / closes[i - 1]).ln())
    if not log_returns:
        return D(0)
    daily_std = _std(log_returns)
    if daily_std <= 0:
        return D(0)
    # Annualize
    annualized = daily_std * D(str(int(trading_days_per_year) ** 0.5))
    return annualized


def detect_regime(
    closes,
    session_date: date,
    lookback_bars: int = 20,
    trading_days_per_year: int = 252,
    envelope_factory=None,
) -> RegimeInfo:
    """Detect the regime for one session and return the matching cost envelope.

    Args:
        closes: last ``lookback_bars`` closing prices (Decimal).
        session_date: the session date for labeling.
        lookback_bars: number of recent bars to use for volatility.
        trading_days_per_year: scaling factor for annualization.
        envelope_factory: optional callable(regime) -> CostEnvelope.
            Defaults to picking from the module-level envelope builders.
    """
    recent = closes[-lookback_bars:] if len(closes) > lookback_bars else closes
    vol = realized_volatility(recent, trading_days_per_year)
    regime = classify_regime(vol)

    if envelope_factory is not None:
        envelope = envelope_factory(regime)
    else:
        from app.backtesting.costs import (
            envelope_low_vol,
            envelope_normal,
            envelope_high_vol,
            envelope_crisis,
        )

        factory_map = {
            "low_vol": envelope_low_vol,
            "normal": envelope_normal,
            "high_vol": envelope_high_vol,
            "crisis": envelope_crisis,
        }
        envelope = factory_map[regime]()

    return RegimeInfo(
        regime=regime,
        realized_vol=vol,
        lookback_bars=len(recent),
        session_date=session_date,
        cost_envelope=envelope,
    )


# ---------------------------------------------------------------------------
# CE/PE grouped multi-day samples
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegimeSample:
    """A grouped set of sessions for one (underlying, option_type, regime) triple."""

    underlying_id: str  # UUID hex
    option_type: str  # CE or PE
    regime: Regime
    session_dates: tuple[date, ...]
    envelopes: tuple[CostEnvelope, ...]
    volatilities: tuple[D, ...]


def group_by_regime_and_type(
    regime_infos: tuple[RegimeInfo, ...],
    underlying_id: str,
    option_types: tuple[str, ...] = ("CE", "PE"),
) -> tuple[RegimeSample, ...]:
    """Group regime info into (option_type, regime) buckets.

    Sessions that share the same (option_type, regime) are collected into
    a RegimeSample.  The caller is expected to have attached an
    ``option_type`` attribute to each RegimeInfo, or we infer it from
    a side-channel.  For simplicity we accept a dict mapping session_date
    → option_type.
    """
    # Build a lookup from session_date → option_type
    # We'll attach option_type to RegimeInfo via a field in the caller.
    # For now, require the caller to pass option_types aligned to regime_infos.
    # Actually, let's store option_type on each RegimeInfo.
    # We need to extend RegimeInfo — let's use a dict-based approach.
    raise NotImplementedError("Use group_samples instead for dict-based grouping")


def group_samples(
    regime_infos: tuple,
    option_type_map: dict,
    underlying_id: str,
) -> tuple:
    """Group regime info into (option_type, regime) buckets.

    Args:
        regime_infos: sequence of RegimeInfo (may have extra attrs).
        option_type_map: dict mapping session_date (date) → option_type (str).
        underlying_id: UUID hex string for grouping.

    Returns:
        Sequence of dicts with keys: option_type, regime, dates, envelopes, vols.
    """
    buckets: dict = {}
    for ri in regime_infos:
        ot = option_type_map.get(ri.session_date, "CE")
        key = (ot, ri.regime)
        if key not in buckets:
            buckets[key] = {
                "option_type": ot,
                "regime": ri.regime,
                "dates": [],
                "envelopes": [],
                "vols": [],
            }
        buckets[key]["dates"].append(ri.session_date)
        buckets[key]["envelopes"].append(ri.cost_envelope)
        buckets[key]["vols"].append(ri.realized_vol)

    return tuple(
        {
            **v,
            "dates": tuple(v["dates"]),
            "envelopes": tuple(v["envelopes"]),
            "vols": tuple(v["vols"]),
        }
        for v in buckets.values()
    )
