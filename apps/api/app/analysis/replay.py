"""Replay boundary for V2.10A — exact historical observation loading.

Loads durable HistoricalObservation rows, reconstructs normalized market
data (NormalizedOptionContract / OptionChainSnapshot) for the replay-time
boundary T0, and exposes them for downstream scanner/analysis consumption.

Zero execution coupling. No future-data leakage.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.discovery.provider import NormalizedOptionContract, OptionChainSnapshot
from datetime import datetime, timezone
from decimal import Decimal

from app.analysis.models import HistoricalObservationModel


def _observation_key(observed_at: datetime) -> str:
    """Normalize observed_at to a consistent ISO string for indexing.

    Strips timezone info so that naive (SQLite) and aware (Python datetime)
    datetimes produce the same key. This is critical because SQLite returns
    naive datetimes even when the column is defined with timezone=True.
    """
    # Normalize to naive UTC: strip tzinfo, yielding a consistent ISO string
    # that matches regardless of how the datetime was originally stored.
    if observed_at.tzinfo is not None:
        observed_at = observed_at.replace(tzinfo=None)
    return observed_at.isoformat()


class ReplayContext:
    """Boundary between durable history and live replay.

    The same production scanner and analysis pipeline consumes this data.
    Replay applies no look-ahead — it only reconstructs what was available
    at each historical timestamp.
    """

    def __init__(self, observations: List[HistoricalObservationModel]):
        self.observations = observations
        # Index observations by canonical_contract_id + observed_at timestamp
        self._index: Dict[tuple[str, str], HistoricalObservationModel] = {}
        for obs in observations:
            # Normalize observed_at to ISO string for key matching across DB drivers
            obs_time_str = _observation_key(obs.observed_at)
            key = (obs.canonical_contract_id, obs_time_str)
            self._index[key] = obs

    def get_observation(self, canonical_contract_id: str, observed_at: datetime) -> Optional[HistoricalObservationModel]:
        obs_time_str = _observation_key(observed_at)
        return self._index.get((canonical_contract_id, obs_time_str))

    @staticmethod
    def _reconstruct_contract(obs: HistoricalObservationModel) -> NormalizedOptionContract:
        return NormalizedOptionContract(
            market=obs.market,
            exchange=obs.exchange,
            underlying=obs.underlying,
            instrument_type=obs.instrument_type,
            expiry=obs.expiry,
            strike=Decimal(str(obs.strike)) if obs.strike is not None else None,
            option_type=obs.option_type,
            canonical_contract_id=obs.canonical_contract_id,
            provider=obs.provider,
            provider_instrument_id=obs.provider_instrument_id,
            last_price=Decimal(str(obs.last_price)) if obs.last_price is not None else None,
            volume=obs.volume if obs.volume is not None else 0,
            open_interest=obs.open_interest if obs.open_interest is not None else 0,
            bid_price=Decimal(str(obs.bid_price)) if obs.bid_price is not None else None,
            ask_price=Decimal(str(obs.ask_price)) if obs.ask_price is not None else None,
            implied_volatility=Decimal(str(obs.implied_volatility)) if obs.implied_volatility is not None else None,
            delta=Decimal(str(obs.delta)) if obs.delta is not None else None,
            gamma=Decimal(str(obs.gamma)) if obs.gamma is not None else None,
            theta=Decimal(str(obs.theta)) if obs.theta is not None else None,
            vega=Decimal(str(obs.vega)) if obs.vega is not None else None,
            lot_size=obs.lot_size if obs.lot_size is not None else 25,
            tick_size=Decimal(str(obs.tick_size)) if obs.tick_size is not None else Decimal("0.05"),
            snapshot_at=obs.observed_at,
        )

    def get_normalized_observation(self, canonical_contract_id: str, observed_at: datetime) -> NormalizedOptionContract:
        obs = self.get_observation(canonical_contract_id, observed_at)
        if obs is None:
            raise KeyError(f"No historical observation at {canonical_contract_id} @ {observed_at}")
        return self._reconstruct_contract(obs)

    def list_observations(self) -> List[HistoricalObservationModel]:
        return sorted(self.observations, key=lambda o: o.observed_at)

    @staticmethod
    def get_scan_context(observations: List[HistoricalObservationModel]) -> OptionChainSnapshot:
        """Build a scan context covering all observations at their timestamps."""
        contracts = [ReplayContext._reconstruct_contract(o) for o in observations]
        snapshot = OptionChainSnapshot(
            underlying="",
            spot_price=None,
            expiry="",
            provider="replay",
            timestamp=None,
            contracts=contracts,
        )
        return snapshot
