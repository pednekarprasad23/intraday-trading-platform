"""Multi-day backtest runner across CE/PE contracts and market regimes.

Runs the offline engine over many sessions grouped by option type (CE / PE)
and market regime, applying the correct cost envelope to each group.
Returns per-group and aggregate results so the caller can compare
how a strategy performs under different cost / regime conditions.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal as D
from uuid import UUID

from app.backtesting.costs import CostEnvelope
from app.backtesting.engine import Result, Metrics, run, SimulationConfig
from app.backtesting.regimes import RegimeInfo, group_samples
from app.historical.reader import VerifiedSession
from app.strategies.contracts import StrategyConfig


@dataclass(frozen=True)
class GroupResult:
    """Results for one (option_type, regime) group."""

    option_type: str
    regime: str
    session_count: int
    sessions: tuple[str, ...]  # ISO date strings
    metrics: Metrics
    result: Result
    cost_envelope: CostEnvelope
    realized_vols: tuple  # Decimal volatilities per session


@dataclass(frozen=True)
class MultiDayReport:
    """Aggregated results across all groups."""

    strategy_id: str
    strategy_version: int
    underlying_id: str
    groups: tuple[GroupResult, ...]
    aggregate_metrics: Metrics
    aggregate_result: Result
    total_sessions: int
    total_trades: int
    cost_envelopes_used: tuple[str, ...]  # unique envelope labels


def _aggregate_metrics(group_results: tuple[GroupResult, ...]) -> tuple[Metrics, Result]:
    """Combine trade-level data across groups into aggregate metrics."""
    all_trades = []
    all_events = []
    all_warnings = set()
    for gr in group_results:
        all_trades.extend(gr.result.trades)
        all_events.extend(gr.result.events)
        all_warnings.update(gr.result.warnings)

    from app.backtesting.engine import metrics as engine_metrics
    from hashlib import sha256
    import json

    aggregate_metrics = engine_metrics(tuple(all_trades))

    # Build a synthetic Result for the aggregate
    # We reuse the engine's metrics function and build a minimal Result
    all_events_tuple = tuple(all_events)
    all_trades_tuple = tuple(all_trades)

    # Fingerprint the aggregate
    input_data = {
        "groups": [
            {
                "option_type": gr.option_type,
                "regime": gr.regime,
                "sessions": gr.sessions,
                "trades": [{"entry": str(t.entry), "exit": str(t.exit),
                            "net_pnl": str(t.net_pnl), "exit_reason": t.exit_reason}
                           for t in gr.result.trades[:50]],
            }
            for gr in group_results
        ]
    }
    fingerprint = sha256(
        json.dumps(input_data, sort_keys=True, default=str).encode()
    ).hexdigest()

    from app.backtesting.engine import Result as EngineResult, ENGINE_VERSION
    aggregate_result = EngineResult(
        events=all_events_tuple,
        trades=all_trades_tuple,
        metrics=aggregate_metrics,
        warnings=tuple(all_warnings),
        fingerprint=fingerprint,
        input_fingerprint="",
    )
    return aggregate_metrics, aggregate_result


def run_multi_day(
    sessions: tuple[VerifiedSession, ...],
    strategy: StrategyConfig,
    regime_infos: tuple[RegimeInfo, ...],
    option_type_map: dict,
    *,
    underlying_id: UUID | None = None,
    quantity: D = D("1"),
    min_sessions_per_group: int = 1,
) -> MultiDayReport:
    """Run backtests across all (option_type, regime) groups.

    Args:
        sessions: all verified sessions to evaluate (must be chronological).
        strategy: the strategy config to test.
        regime_infos: regime detection results, one per session date.
        option_type_map: mapping from session_date → option_type (CE/PE).
        underlying_id: optional UUID for contract metadata validation.
        quantity: lot quantity per trade.
        min_sessions_per_group: skip groups with fewer sessions.

    Returns:
        MultiDayReport with per-group and aggregate metrics.
    """
    if not sessions:
        raise ValueError("At least one session required")
    if len(sessions) > 100:
        raise ValueError("Maximum 100 sessions per multi-day run")

    # Build date → session lookup
    date_to_session: dict = {}
    for s in sessions:
        date_to_session[s.source.session_date] = s

    # Build date → regime lookup
    date_to_regime: dict = {}
    for ri in regime_infos:
        date_to_regime[ri.session_date] = ri

    # Group sessions by (option_type, regime)
    buckets: dict = {}
    for s in sessions:
        sd = s.source.session_date
        ot = option_type_map.get(sd, "CE")
        ri = date_to_regime.get(sd)
        if ri is None:
            raise ValueError(f"No regime info for session date {sd}")
        key = (ot, ri.regime)
        if key not in buckets:
            buckets[key] = {"sessions": [], "regime_info": ri}
        buckets[key]["sessions"].append(s)

    if not buckets:
        raise ValueError("No valid groups produced")

    # Run backtests per group
    group_results: list = []
    for (ot, regime), bucket in sorted(buckets.items()):
        group_sessions = tuple(bucket["sessions"])
        if len(group_sessions) < min_sessions_per_group:
            continue

        ri = bucket["regime_info"]
        config = ri.cost_envelope.to_simulation_config(quantity)

        # Validate contract metadata
        uid = None
        strike = None
        otype = None
        if underlying_id is not None:
            uid = underlying_id
        if len(group_sessions) > 0:
            strike = group_sessions[0].strike_price
            otype = group_sessions[0].source.option_type

        result = run(
            group_sessions,
            strategy,
            config,
            underlying_id=uid,
            strike=strike,
            option_type=otype,
        )

        group_results.append(
            GroupResult(
                option_type=ot,
                regime=regime,
                session_count=len(group_sessions),
                sessions=tuple(s.source.session_date.isoformat() for s in group_sessions),
                metrics=result.metrics,
                result=result,
                cost_envelope=ri.cost_envelope,
                realized_vols=(ri.realized_vol,),
            )
        )

    if not group_results:
        raise ValueError("No groups met the minimum session threshold")

    # Aggregate across groups
    aggregate_metrics, aggregate_result = _aggregate_metrics(tuple(group_results))

    return MultiDayReport(
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.version,
        underlying_id=underlying_id.hex if underlying_id else "",
        groups=tuple(group_results),
        aggregate_metrics=aggregate_metrics,
        aggregate_result=aggregate_result,
        total_sessions=sum(g.session_count for g in group_results),
        total_trades=sum(g.result.metrics.trade_count for g in group_results),
        cost_envelopes_used=tuple(
            dict.fromkeys(g.cost_envelope.label for g in group_results)
        ),
    )
