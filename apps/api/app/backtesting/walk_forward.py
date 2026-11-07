"""Chronological non-overlapping out-of-sample folds; no test data in selection."""

from dataclasses import dataclass
from app.backtesting.engine import Result, SimulationConfig, run
from app.historical.reader import VerifiedSession
from app.strategies.contracts import StrategyConfig


@dataclass(frozen=True)
class Fold:
    training_dates: tuple[str, ...]
    test_dates: tuple[str, ...]
    chosen: StrategyConfig
    training: Result
    test: Result


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
