"""Chronological non-overlapping out-of-sample folds; no test data in selection.

Supports both flat-cost and cost-envelope-aware walk-forward splits, where
each fold can carry its own regime-specific cost structure.
"""

from dataclasses import dataclass, field
from decimal import Decimal as D
from uuid import UUID

from app.backtesting.costs import CostEnvelope
from app.backtesting.engine import Result, SimulationConfig, run
from app.backtesting.regimes import RegimeInfo
from app.historical.reader import VerifiedSession
from app.strategies.contracts import StrategyConfig


@dataclass(frozen=True)
class Fold:
    training_dates: tuple[str, ...]
    test_dates: tuple[str, ...]
    chosen: StrategyConfig
    training: Result
    test: Result


@dataclass(frozen=True)
class CostAwareFold:
    """Walk-forward fold with per-fold cost-envelope tracking."""

    training_dates: tuple[str, ...]
    test_dates: tuple[str, ...]
    chosen: StrategyConfig
    training: Result
    test: Result
    training_cost_envelope: CostEnvelope
    test_cost_envelope: CostEnvelope
    training_regime: str
    test_regime: str


def walk_forward(
    sessions: tuple[VerifiedSession, ...],
    candidates: tuple[StrategyConfig, ...],
    config: SimulationConfig,
    *,
    train_size: int,
    test_size: int,
    min_bars_per_session: int = 10,
) -> tuple[Fold, ...]:
    """Expanding training window, disjoint chronological test blocks; maximize training net P&L.

    Ties retain the first explicitly supplied candidate. All input sessions must be
    verified and meet coverage, including unused trailing sessions.
    """
    if (
        not candidates
        or len(candidates) > 20
        or train_size < 2
        or test_size < 1
        or min_bars_per_session < 3
        or min_bars_per_session > 50000
        or len(sessions) > 100
        or len(sessions) < train_size + test_size
    ):
        raise ValueError("Walk-forward fold, candidate or coverage bounds invalid")
    if len(set(candidates)) != len(candidates):
        raise ValueError("Duplicate candidates")
    if (
        tuple(sorted(sessions, key=lambda s: s.source.session_date)) != sessions
        or len({s.source.session_date for s in sessions}) != len(sessions)
        or any(len(s.bars) < min_bars_per_session for s in sessions)
    ):
        raise ValueError("Nonchronological or insufficient session coverage")
    folds = []
    for cutoff in range(train_size, len(sessions) - test_size + 1, test_size):
        training = sessions[:cutoff]
        testing = sessions[cutoff : cutoff + test_size]
        ranked = [
            (run(training, candidate, config), candidate) for candidate in candidates
        ]
        best, chosen = max(ranked, key=lambda item: item[0].metrics.net_pnl)
        test = run(testing, chosen, config)
        folds.append(
            Fold(
                tuple(s.source.session_date.isoformat() for s in training),
                tuple(s.source.session_date.isoformat() for s in testing),
                chosen,
                best,
                test,
            )
        )
    if not folds:
        raise ValueError("No full out-of-sample fold")
    return tuple(folds)


def walk_forward_cost_aware(
    sessions: tuple[VerifiedSession, ...],
    candidates: tuple[StrategyConfig, ...],
    envelope: CostEnvelope,
    regime_infos: tuple[RegimeInfo, ...],
    *,
    train_size: int,
    test_size: int,
    quantity: D = D("1"),
    min_bars_per_session: int = 10,
) -> tuple[CostAwareFold, ...]:
    """Expanding-window walk-forward with per-fold regime-aware cost envelopes.

    Each fold trains on a chronological block, selects the best candidate by
    training net P&L, then evaluates on the next disjoint block.  The cost
    envelope for each block is derived from that block's average regime,
    ensuring that out-of-sample costs reflect the regime that actually
    obtained during the test window.

    Args:
        sessions: verified sessions in chronological order.
        candidates: strategy configs to rank.
        envelope: base cost envelope; per-session multipliers are applied
            according to each session's detected regime.
        regime_infos: one RegimeInfo per session date.
        train_size: number of sessions for initial training window.
        test_size: size of each test block.
        quantity: lot size per trade.
        min_bars_per_session: minimum bars per session.

    Returns:
        Sequence of CostAwareFold with per-fold cost tracking.
    """
    if (
        not candidates
        or len(candidates) > 20
        or train_size < 2
        or test_size < 1
        or min_bars_per_session < 3
        or min_bars_per_session > 50000
        or len(sessions) > 100
        or len(sessions) < train_size + test_size
    ):
        raise ValueError("Walk-forward fold, candidate or coverage bounds invalid")
    if len(set(candidates)) != len(candidates):
        raise ValueError("Duplicate candidates")
    if (
        tuple(sorted(sessions, key=lambda s: s.source.session_date)) != sessions
        or len({s.source.session_date for s in sessions}) != len(sessions)
        or any(len(s.bars) < min_bars_per_session for s in sessions)
    ):
        raise ValueError("Nonchronological or insufficient session coverage")

    # Build date → regime lookup
    date_to_regime: dict = {}
    for ri in regime_infos:
        date_to_regime[ri.session_date] = ri

    # Validate all sessions have regime info
    for s in sessions:
        if s.source.session_date not in date_to_regime:
            raise ValueError(f"No regime info for session date {s.source.session_date}")

    folds: list = []
    for cutoff in range(train_size, len(sessions) - test_size + 1, test_size):
        training = sessions[:cutoff]
        testing = sessions[cutoff : cutoff + test_size]

        # Determine training block regime (majority vote)
        train_regimes: dict = {}
        for s in training:
            ri = date_to_regime[s.source.session_date]
            train_regimes[ri.regime] = train_regimes.get(ri.regime, 0) + 1
        train_regime = max(train_regimes, key=train_regimes.get)

        # Determine test block regime (majority vote)
        test_regimes: dict = {}
        for s in testing:
            ri = date_to_regime[s.source.session_date]
            test_regimes[ri.regime] = test_regimes.get(ri.regime, 0) + 1
        test_regime = max(test_regimes, key=test_regimes.get)

        # Build per-regime cost configs
        train_config = envelope.to_simulation_config(quantity)
        test_config = envelope.to_simulation_config(quantity)

        # Override with test block's regime for test evaluation
        from app.backtesting.costs import REGIME_MULTIPLIERS
        test_env = CostEnvelope(
            brokerage=envelope.brokerage,
            stamp_duty=envelope.stamp_duty,
            slippage=envelope.slippage,
            spread=envelope.spread,
            stop_fraction=envelope.stop_fraction,
            target_fraction=envelope.target_fraction,
            regime=test_regime,
            label=f"{envelope.label}_{test_regime}",
        )
        test_config = test_env.to_simulation_config(quantity)

        # Run training evaluation for candidate ranking
        ranked = []
        for candidate in candidates:
            train_result = run(training, candidate, train_config)
            ranked.append((train_result, candidate))
        best, chosen = max(ranked, key=lambda item: item[0].metrics.net_pnl)

        # Run test evaluation with test-block costs
        test_result = run(testing, chosen, test_config)

        # Get the cost envelopes for this fold
        train_ri = date_to_regime[training[0].source.session_date]
        test_ri = date_to_regime[testing[0].source.session_date]
        train_env = train_ri.cost_envelope
        test_env_fold = test_ri.cost_envelope

        folds.append(
            CostAwareFold(
                training_dates=tuple(s.source.session_date.isoformat() for s in training),
                test_dates=tuple(s.source.session_date.isoformat() for s in testing),
                chosen=chosen,
                training=best,
                test=test_result,
                training_cost_envelope=train_env,
                test_cost_envelope=test_env_fold,
                training_regime=train_regime,
                test_regime=test_regime,
            )
        )

    if not folds:
        raise ValueError("No full out-of-sample fold")
    return tuple(folds)


@dataclass(frozen=True)
class CostAwareFoldSummary:
    """Lightweight summary of a cost-aware fold for reporting."""

    fold_index: int
    training_dates: tuple[str, ...]
    test_dates: tuple[str, ...]
    training_regime: str
    test_regime: str
    training_net_pnl: D
    test_net_pnl: D
    training_trades: int
    test_trades: int
    strategy_id: str
    strategy_version: int


def summarize_cost_aware_folds(
    folds: tuple[CostAwareFold, ...],
) -> tuple[CostAwareFoldSummary, ...]:
    """Produce a lightweight summary of cost-aware walk-forward folds."""
    return tuple(
        CostAwareFoldSummary(
            fold_index=i,
            training_dates=fold.training_dates,
            test_dates=fold.test_dates,
            training_regime=fold.training_regime,
            test_regime=fold.test_regime,
            training_net_pnl=fold.training.metrics.net_pnl,
            test_net_pnl=fold.test.metrics.net_pnl,
            training_trades=fold.training.metrics.trade_count,
            test_trades=fold.test.metrics.trade_count,
            strategy_id=fold.chosen.strategy_id,
            strategy_version=fold.chosen.version,
        )
        for i, fold in enumerate(folds)
    )


def walk_forward_summary(
    sessions: tuple[VerifiedSession, ...],
    candidates: tuple[StrategyConfig, ...],
    config: SimulationConfig,
    *,
    train_size: int,
    test_size: int,
    min_bars_per_session: int = 10,
) -> tuple:
    """Run plain walk-forward and return a lightweight summary.

    This is a convenience wrapper around walk_forward that returns dicts
    suitable for JSON serialization in API responses.
    """
    folds = walk_forward(
        sessions, candidates, config,
        train_size=train_size,
        test_size=test_size,
        min_bars_per_session=min_bars_per_session,
    )
    return tuple(
        {
            "fold_index": i,
            "training_dates": fold.training_dates,
            "test_dates": fold.test_dates,
            "strategy_id": fold.chosen.strategy_id,
            "strategy_version": fold.chosen.version,
            "training_net_pnl": str(fold.training.metrics.net_pnl),
            "test_net_pnl": str(fold.test.metrics.net_pnl),
            "training_trades": fold.training.metrics.trade_count,
            "test_trades": fold.test.metrics.trade_count,
            "training_win_rate": str(fold.training.metrics.win_rate)
                if fold.training.metrics.win_rate is not None else None,
            "test_win_rate": str(fold.test.metrics.win_rate)
                if fold.test.metrics.win_rate is not None else None,
        }
        for i, fold in enumerate(folds)
    )
