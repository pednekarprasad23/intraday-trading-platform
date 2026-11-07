"""Cost structures for backtesting: fees, taxes, slippage, spread, regime multipliers.

Every cost component is a Decimal so that net P&L arithmetic is exact.
Regime multipliers scale variable costs (slippage, spread) when volatility
or liquidity conditions make execution harder. Fixed costs (brokerage, stamp
duty) are applied per-trade regardless of regime.
"""

from dataclasses import dataclass, field
from decimal import Decimal as D
from typing import Literal

from app.backtesting.engine import SimulationConfig

# ---------------------------------------------------------------------------
# Fixed per-trade costs (applied once per side or per trade pair)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Brokerage:
    """Flat brokerage per side, or a percentage of turnover capped at a max."""

    flat_per_side: D = D("0")
    pct_turnover: D = D("0")
    cap_per_trade: D = D("0")

    def charge(self, turnover: D) -> D:
        charge = self.flat_per_side + turnover * self.pct_turnover
        if self.cap_per_trade > 0:
            charge = min(charge, self.cap_per_trade)
        return charge


@dataclass(frozen=True)
class StampDuty:
    """Stamp duty — currently only on equity sell-side in India."""

    rate: D = D("0")  # e.g. D("0.00015") for 0.015 %

    def charge(self, turnover: D) -> D:
        return turnover * self.rate


# ---------------------------------------------------------------------------
# Variable costs (per-unit, scaled by regime)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SlippageModel:
    """Per-unit slippage with optional regime multiplier."""

    base_per_unit: D
    regime_multiplier: D = D("1")

    def per_unit(self) -> D:
        return self.base_per_unit * self.regime_multiplier


@dataclass(frozen=True)
class SpreadModel:
    """Half-spread per-unit with optional regime multiplier."""

    base_half_spread: D
    regime_multiplier: D = D("1")

    def half_spread(self) -> D:
        return self.base_half_spread * self.regime_multiplier


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------

Regime = Literal["low_vol", "normal", "high_vol", "crisis"]

REGIME_MULTIPLIERS: dict[Regime, dict[str, D]] = {
    "low_vol": {"slippage": D("0.5"), "spread": D("0.7")},
    "normal": {"slippage": D("1"), "spread": D("1")},
    "high_vol": {"slippage": D("2"), "spread": D("1.5")},
    "crisis": {"slippage": D("4"), "spread": D("2.5")},
}


@dataclass(frozen=True)
class CostEnvelope:
    """All costs for one backtest leg, including regime flags.

    The ``regime`` field is advisory — the engine does not infer regime from
    price action. Callers set it to reflect the market regime during the
    session window.
    """

    brokerage: Brokerage
    stamp_duty: StampDuty
    slippage: SlippageModel
    spread: SpreadModel
    stop_fraction: D
    target_fraction: D
    regime: Regime = "normal"
    label: str = ""

    def to_simulation_config(self, quantity: D) -> SimulationConfig:
        """Convert this envelope into a plain SimulationConfig.

        Uses the regime's multipliers to resolve slippage and spread to
        concrete per-unit values.
        """
        mults = REGIME_MULTIPLIERS[self.regime]
        return SimulationConfig(
            quantity=quantity,
            fee_per_side=self.brokerage.flat_per_side,
            tax_rate=self.stamp_duty.rate,
            slippage_per_unit=self.slippage.per_unit() * mults["slippage"],
            spread_per_unit=self.spread.half_spread() * 2 * mults["spread"],
            stop_fraction=self.stop_fraction,
            target_fraction=self.target_fraction,
        )

    def brokerage_charge(self, turnover: D) -> D:
        return self.brokerage.charge(turnover)

    def stamp_charge(self, turnover: D) -> D:
        return self.stamp_duty.charge(turnover)

    def total_variable_cost_per_unit(self) -> D:
        mults = REGIME_MULTIPLIERS[self.regime]
        return (
            self.slippage.per_unit() * mults["slippage"]
            + self.spread.half_spread() * mults["spread"]
        )


# ---------------------------------------------------------------------------
# Pre-built envelopes for common Indian options scenarios
# ---------------------------------------------------------------------------

def _brokerage_flat(flat: D = D("20")) -> Brokerage:
    return Brokerage(flat_per_side=flat)


def _stamp_duty(rate: D = D("0.00015")) -> StampDuty:
    return StampDuty(rate=rate)


def envelope_low_vol(
    quantity: D = D("1"),
) -> CostEnvelope:
    """Low-volatility regime: tight spreads, minimal slippage."""
    return CostEnvelope(
        brokerage=_brokerage_flat(D("20")),
        stamp_duty=_stamp_duty(),
        slippage=SlippageModel(D("0.05")),
        spread=SpreadModel(D("0.10")),
        stop_fraction=D("0.02"),
        target_fraction=D("0.04"),
        regime="low_vol",
        label="low_vol",
    )


def envelope_normal(
    quantity: D = D("1"),
) -> CostEnvelope:
    """Normal market conditions."""
    return CostEnvelope(
        brokerage=_brokerage_flat(D("20")),
        stamp_duty=_stamp_duty(),
        slippage=SlippageModel(D("0.10")),
        spread=SpreadModel(D("0.20")),
        stop_fraction=D("0.02"),
        target_fraction=D("0.04"),
        regime="normal",
        label="normal",
    )


def envelope_high_vol(
    quantity: D = D("1"),
) -> CostEnvelope:
    """High volatility: wider spreads, more slippage."""
    return CostEnvelope(
        brokerage=_brokerage_flat(D("20")),
        stamp_duty=_stamp_duty(),
        slippage=SlippageModel(D("0.25")),
        spread=SpreadModel(D("0.50")),
        stop_fraction=D("0.03"),
        target_fraction=D("0.06"),
        regime="high_vol",
        label="high_vol",
    )


def envelope_crisis(
    quantity: D = D("1"),
) -> CostEnvelope:
    """Stress / crisis regime: severe slippage and spread widening."""
    return CostEnvelope(
        brokerage=_brokerage_flat(D("20")),
        stamp_duty=_stamp_duty(),
        slippage=SlippageModel(D("0.50")),
        spread=SpreadModel(D("1.00")),
        stop_fraction=D("0.05"),
        target_fraction=D("0.10"),
        regime="crisis",
        label="crisis",
    )


def envelope_from_simulation(config: SimulationConfig, regime: Regime = "normal") -> CostEnvelope:
    """Reverse-engineer a CostEnvelope from an existing SimulationConfig.

    Handy for converting between the old flat API and the new regime-aware
    envelope.  The brokerage flat is recovered from ``fee_per_side`` and
    stamp duty from ``tax_rate``; slippage and spread are de-multiplied
    assuming the given regime's multiplier.
    """
    mults = REGIME_MULTIPLIERS[regime]
    base_slippage = config.slippage_per_unit / mults["slippage"] if mults["slippage"] else config.slippage_per_unit
    base_spread = (config.spread_per_unit / 2) / mults["spread"] if mults["spread"] else config.spread_per_unit / 2
    return CostEnvelope(
        brokerage=Brokerage(flat_per_side=config.fee_per_side),
        stamp_duty=StampDuty(rate=config.tax_rate),
        slippage=SlippageModel(base_slippage),
        spread=SpreadModel(base_spread),
        stop_fraction=config.stop_fraction,
        target_fraction=config.target_fraction,
        regime=regime,
        label=regime,
    )
