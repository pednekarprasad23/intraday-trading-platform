"""Explicit built-in registry and bounded option-premium decision evaluation."""

from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.strategies.contracts import Candle, Decision, Source, StrategyConfig
from app.strategies.indicators import ema, rsi

STRATEGY_ID = "option-premium-ema-rsi"
VERSION = 1
REGISTRY = {
    (
        STRATEGY_ID,
        VERSION,
    ): "Long premium when fast EMA exceeds slow EMA and RSI is bounded"
}
MAX_BARS = 500
MAX_PERIOD = 100


def validate_config(config: StrategyConfig, timeframe: str) -> int:
    if (config.strategy_id, config.version) not in REGISTRY:
        raise ValueError("Unsupported strategy ID/version")
    if timeframe not in {"1m", "5m"}:
        raise ValueError("Unsupported timeframe")
    if not (2 <= config.fast_period < config.slow_period <= MAX_PERIOD):
        raise ValueError("EMA periods must satisfy 2 <= fast < slow <= 100")
    if not (2 <= config.rsi_period <= MAX_PERIOD):
        raise ValueError("RSI period must be 2..100")
    if any(
        not isinstance(v, Decimal) or not v.is_finite()
        for v in (config.rsi_floor, config.rsi_ceiling)
    ) or not (Decimal(0) <= config.rsi_floor < config.rsi_ceiling <= Decimal(100)):
        raise ValueError("RSI bounds must be finite Decimal values within 0..100")
    return max(config.slow_period, config.rsi_period + 1)


def evaluate(
    config: StrategyConfig, source: Source, bars: tuple[Candle, ...]
) -> Decision:
    """Only the last completed bar is considered; no fill or trading instruction."""
    required = validate_config(config, source.timeframe)
    if len(bars) > MAX_BARS:
        raise ValueError("Window exceeds evaluation limit")
    if (
        source.option_type not in {"CE", "PE"}
        or not source.provider
        or not source.provider_key
    ):
        raise ValueError("Verified option source required")
    if (
        len(source.partition_sha256) != 64
        or len(source.source_sha256) != 64
        or any(
            c not in "0123456789abcdef"
            for c in source.partition_sha256 + source.source_sha256
        )
    ):
        raise ValueError("Valid provenance checksums required")
    step = timedelta(minutes=int(source.timeframe[0]))
    decision_time = bars[-1].bar_time + step if bars else None
    reasons = []
    if len(bars) < required:
        reasons.append("INSUFFICIENT_HISTORY")
    if bars and any(
        bar.bar_time.astimezone(ZoneInfo("Asia/Kolkata")).date() != source.session_date
        or bar.bar_time.astimezone(ZoneInfo("Asia/Kolkata")).date() > source.expiry_date
        for bar in bars
    ):
        reasons.append("SESSION_OR_EXPIRY_MISMATCH")
    if any(
        bars[i].bar_time - bars[i - 1].bar_time != step for i in range(1, len(bars))
    ):
        reasons.append("GAP_OR_DUPLICATE")
    if any(bar.volume is None for bar in bars):
        reasons.append("MISSING_VOLUME")
    if reasons:
        return Decision(
            1,
            config,
            source,
            bars,
            required,
            decision_time,
            "NONE",
            "REJECTED",
            tuple(reasons),
        )
    closes = tuple(bar.close for bar in bars)
    fast = ema(closes, config.fast_period)
    slow = ema(closes, config.slow_period)
    strength = rsi(closes, config.rsi_period)
    direction = (
        "LONG"
        if fast > slow and config.rsi_floor <= strength <= config.rsi_ceiling
        else "NONE"
    )
    return Decision(
        1,
        config,
        source,
        bars,
        required,
        decision_time,
        direction,
        "VALID",
        (),
        fast,
        slow,
        strength,
    )
