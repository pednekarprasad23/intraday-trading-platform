"""Pure Decimal indicators; None means insufficient or undefined input."""

from decimal import Decimal

from app.strategies.contracts import Candle


ZERO = Decimal(0)
HUNDRED = Decimal(100)


def ema(values: tuple[Decimal | None, ...], period: int) -> Decimal | None:
    if (
        period < 1
        or len(values) < period
        or any(v is None or not v.is_finite() for v in values)
    ):
        return None
    seed = sum(values[:period], ZERO) / period
    factor = Decimal(2) / (period + 1)
    for value in values[period:]:
        seed += (value - seed) * factor
    return seed


def rsi(values: tuple[Decimal | None, ...], period: int) -> Decimal | None:
    if (
        period < 1
        or len(values) <= period
        or any(v is None or not v.is_finite() for v in values)
    ):
        return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = sum((max(x, ZERO) for x in changes[:period]), ZERO) / period
    losses = sum((max(-x, ZERO) for x in changes[:period]), ZERO) / period
    for change in changes[period:]:
        gains = (gains * (period - 1) + max(change, ZERO)) / period
        losses = (losses * (period - 1) + max(-change, ZERO)) / period
    if losses == 0:
        return Decimal(50) if gains == 0 else HUNDRED
    return HUNDRED - HUNDRED / (1 + gains / losses)


def atr(bars: tuple[Candle, ...], period: int) -> Decimal | None:
    if period < 1 or len(bars) <= period:
        return None
    ranges = [
        max(
            bar.high - bar.low,
            abs(bar.high - bars[i - 1].close),
            abs(bar.low - bars[i - 1].close),
        )
        for i, bar in enumerate(bars)
        if i > 0
    ]
    result = sum(ranges[:period], ZERO) / period
    for value in ranges[period:]:
        result = (result * (period - 1) + value) / period
    return result


def vwap(bars: tuple[Candle, ...]) -> Decimal | None:
    if not bars or any(bar.volume is None for bar in bars):
        return None
    total = sum((bar.volume for bar in bars), ZERO)
    if total == 0:
        return None
    return (
        sum((((bar.high + bar.low + bar.close) / 3) * bar.volume for bar in bars), ZERO)
        / total
    )
