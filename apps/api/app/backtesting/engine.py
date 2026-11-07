"""Deterministic offline long-premium simulation; never an order or broker fill."""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.historical.reader import VerifiedSession
from app.strategies.contracts import StrategyConfig
from app.strategies.engine import evaluate, validate_config

D = Decimal
ENGINE_VERSION = "offline-premium-v1"
MAX_BARS = 50_000


def fingerprint(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class SimulationConfig:
    quantity: Decimal
    fee_per_side: Decimal
    tax_rate: Decimal
    slippage_per_unit: Decimal
    spread_per_unit: Decimal
    stop_fraction: Decimal
    target_fraction: Decimal

    def __post_init__(self):
        for name in (
            "quantity",
            "fee_per_side",
            "tax_rate",
            "slippage_per_unit",
            "spread_per_unit",
            "stop_fraction",
            "target_fraction",
        ):
            value = getattr(self, name)
            if not isinstance(value, D) or not value.is_finite():
                raise ValueError(f"Finite Decimal required: {name}")
        if (
            self.quantity <= 0
            or self.quantity > 100_000
            or self.fee_per_side < 0
            or self.slippage_per_unit < 0
            or self.spread_per_unit < 0
            or not 0 <= self.tax_rate <= D("1")
            or not 0 < self.stop_fraction < D("1")
            or not 0 < self.target_fraction <= D("10")
        ):
            raise ValueError("Simulation cost / quantity / exit bounds invalid")


@dataclass(frozen=True)
class Event:
    time: datetime
    kind: str
    session_date: str
    bar_index: int
    price: Decimal | None
    reason: str


@dataclass(frozen=True)
class Trade:
    entry_time: datetime
    exit_time: datetime
    entry: Decimal
    exit: Decimal
    quantity: Decimal
    net_pnl: Decimal
    exit_reason: str


@dataclass(frozen=True)
class Metrics:
    net_pnl: Decimal
    expectancy: Decimal | None
    win_rate: Decimal | None
    profit_factor: Decimal | None
    max_drawdown: Decimal
    longest_losing_streak: int
    trade_count: int


@dataclass(frozen=True)
class Result:
    events: tuple[Event, ...]
    trades: tuple[Trade, ...]
    metrics: Metrics
    warnings: tuple[str, ...]
    fingerprint: str
    input_fingerprint: str


def metrics(trades: tuple[Trade, ...]) -> Metrics:
    net = sum((t.net_pnl for t in trades), D(0))
    gross_win = sum((t.net_pnl for t in trades if t.net_pnl > 0), D(0))
    gross_loss = -sum((t.net_pnl for t in trades if t.net_pnl < 0), D(0))
    equity = peak = drawdown = D(0)
    streak = longest = 0
    for trade in trades:
        equity += trade.net_pnl
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
        streak = streak + 1 if trade.net_pnl < 0 else 0
        longest = max(longest, streak)
    count = len(trades)
    return Metrics(
        net,
        net / count if count else None,
        D(sum(t.net_pnl > 0 for t in trades)) / count if count else None,
        gross_win / gross_loss if gross_loss else None,
        drawdown,
        longest,
        count,
    )


def run(
    sessions: tuple[VerifiedSession, ...],
    strategy: StrategyConfig,
    config: SimulationConfig,
    *,
    underlying_id=None,
    strike=None,
    option_type=None,
) -> Result:
    """Only contiguous completed bars decide; next open is earliest possible fill.

    Entry and exit are confined to one verified session. Stop wins when both
    stop and target touch. Missing next bar never creates a synthetic exit.
    """
    if (
        not sessions
        or len(sessions) > 100
        or sum(len(s.bars) for s in sessions) > MAX_BARS
    ):
        raise ValueError("Backtest requires 1..100 sessions and at most 50000 bars")
    if tuple(sorted(sessions, key=lambda s: s.source.session_date)) != sessions or len(
        {s.source.session_date for s in sessions}
    ) != len(sessions):
        raise ValueError("Sessions must be unique and chronological")
    provider = sessions[0].source.provider
    timeframe = sessions[0].source.timeframe
    instrument_id = sessions[0].source.instrument_id
    required = validate_config(strategy, timeframe)
    if any(
        s.source.provider != provider
        or s.source.timeframe != timeframe
        or s.source.instrument_id != instrument_id
        for s in sessions
    ):
        raise ValueError("Mixing providers, timeframes or contracts forbidden")
    if (
        underlying_id is not None
        and any(s.underlying_id != underlying_id for s in sessions)
        or strike is not None
        and any(s.strike_price != strike for s in sessions)
        or option_type is not None
        and any(s.source.option_type != option_type for s in sessions)
    ):
        raise ValueError("Contract selection metadata mismatch")
    input_hash = fingerprint(
        [
            {
                "source": asdict(s.source),
                "bars": [asdict(b) for b in s.bars],
                "underlying": s.underlying_id,
                "strike": s.strike_price,
                "end": s.session_end,
            }
            for s in sessions
        ]
    )
    events: list[Event] = []
    trades: list[Trade] = []
    warnings = [
        "OHLCV-only simulated fills; liquidity, spread, slippage and costs are assumptions"
    ]
    step = timedelta(minutes=int(timeframe[0]))
    for session in sessions:
        bars = session.bars
        day = session.source.session_date.isoformat()
        if (
            not bars
            or any(
                bars[i].bar_time != bars[0].bar_time + step * i
                for i in range(len(bars))
            )
            or bars[-1].bar_time + step != session.session_end
        ):
            raise ValueError("Incomplete or gapped session")
        if day > session.source.expiry_date.isoformat():
            raise ValueError("Session after option expiry")
        entry = None
        pending = False
        for i, bar in enumerate(bars):
            # Open-time fills happen before completion-time decisions for this bar.
            if pending:
                pending = False
                if i == len(bars) - 1:
                    events.append(
                        Event(bar.bar_time, "NO_FILL", day, i, None, "NO_EXIT_BAR")
                    )
                else:
                    price = (
                        bar.open + config.slippage_per_unit + config.spread_per_unit / 2
                    )
                    entry = (bar.bar_time, price)
                    events.append(
                        Event(
                            bar.bar_time,
                            "ENTRY",
                            day,
                            i,
                            price,
                            "NEXT_BAR_OPEN_ASSUMED",
                        )
                    )
            if entry is not None:
                opened, paid = entry
                stop = paid * (1 - config.stop_fraction)
                target = paid * (1 + config.target_fraction)
                # Entry bar's OHLC spans both before and after entry; ignore its
                # high/low entirely. Subsequent bar gap-through exits use its open.
                reason = None
                raw_exit = None
                if i > 0 and bar.bar_time > opened:
                    if bar.open <= stop:
                        raw_exit, reason = bar.open, "GAP_STOP"
                    elif bar.open >= target:
                        raw_exit, reason = target, "GAP_TARGET_CAPPED"
                    elif bar.low <= stop:
                        raw_exit, reason = (
                            stop,
                            "STOP_AMBIGUOUS" if bar.high >= target else "STOP",
                        )
                    elif bar.high >= target:
                        raw_exit, reason = target, "TARGET"
                if i == len(bars) - 1 and reason is None:
                    raw_exit, reason = bar.close, "SESSION_OR_EXPIRY_CLOSE_ASSUMED"
                if reason is not None:
                    # OHLC-only thresholds are conservatively priced, never exchange fills.
                    at = bar.bar_time + step
                    received = max(
                        D(0),
                        raw_exit
                        - config.slippage_per_unit
                        - config.spread_per_unit / 2,
                    )
                    turnover = (paid + received) * config.quantity
                    pnl = (
                        (received - paid) * config.quantity
                        - 2 * config.fee_per_side
                        - turnover * config.tax_rate
                    )
                    trades.append(
                        Trade(opened, at, paid, received, config.quantity, pnl, reason)
                    )
                    events.append(Event(at, "EXIT", day, i, received, reason))
                    entry = None
            # A bar labeled at its opening becomes visible at its end.
            if (
                entry is None
                and not pending
                and i + 1 < len(bars)
                and i + 1 >= required
            ):
                decision = evaluate(
                    strategy, session.source, bars[max(0, i + 1 - 500) : i + 1]
                )
                if decision.quality == "VALID" and decision.direction == "LONG":
                    pending = True
                    events.append(
                        Event(
                            bar.bar_time + step, "SIGNAL", day, i, None, "COMPLETED_BAR"
                        )
                    )
        if entry is not None:
            raise ValueError("No completed exit bar available")
    ledger = tuple(events)
    trades_tuple = tuple(trades)
    digest = fingerprint(
        {
            "engine": ENGINE_VERSION,
            "inputs": input_hash,
            "strategy": asdict(strategy),
            "simulation": asdict(config),
            "events": [asdict(e) for e in ledger],
            "trades": [asdict(t) for t in trades_tuple],
        }
    )
    return Result(
        ledger, trades_tuple, metrics(trades_tuple), tuple(warnings), digest, input_hash
    )
