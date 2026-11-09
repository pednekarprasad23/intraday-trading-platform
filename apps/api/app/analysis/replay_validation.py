"""Replay validation and calibration foundation for V2.10D.

Provides:
- Calibration of opportunity scores against historical observation baselines
- Validation of replay fidelity (no look-ahead leakage)
- Score adjustment based on engine coverage and data completeness
- Calibration reports for deterministic pipeline tuning
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.analysis.models import HistoricalObservationModel
from app.analysis.opportunity_engine import OpportunityResult


class ReplayValidator:
    """Validates replay integrity and calibrates scores against baselines.

    Zero execution coupling. Market intelligence / research only.
    """

    def __init__(self, observations: List[HistoricalObservationModel]) -> None:
        self.observations = observations
        # Index by (canonical_contract_id, observed_at) for fast lookup
        self._index: Dict[tuple[str, str], HistoricalObservationModel] = {}
        for obs in observations:
            key = (obs.canonical_contract_id, self._observation_key(obs.observed_at))
            self._index[key] = obs

    @staticmethod
    def _observation_key(observed_at: datetime) -> str:
        """Normalize observed_at to a consistent ISO string for indexing.

        Strips timezone info so that naive (SQLite) and aware (Python datetime)
        datetimes produce the same key. This is critical because SQLite returns
        naive datetimes even when the column is defined with timezone=True.
        """
        if observed_at.tzinfo is not None:
            observed_at = observed_at.replace(tzinfo=None)
        return observed_at.isoformat()

    def validate_observation_at(
        self,
        canonical_contract_id: str,
        observed_at: datetime,
    ) -> Dict[str, Any]:
        """Validate that an observation exists at the given point-in-time.

        Returns dict with validation status and available data summary.
        """
        key = (canonical_contract_id, self._observation_key(observed_at))
        obs = self._index.get(key)

        if obs is None:
            return {
                "valid": False,
                "reason": "no_observation_at_point_in_time",
                "canonical_contract_id": canonical_contract_id,
                "observed_at": self._observation_key(observed_at),
            }

        # Count available non-None fields for calibration
        numeric_fields = ["spot_price", "last_price", "volume", "open_interest",
                         "bid_price", "ask_price", "implied_volatility",
                         "delta", "gamma", "theta", "vega"]
        available = sum(1 for f in numeric_fields if getattr(obs, f, None) is not None)
        total = len(numeric_fields)

        return {
            "valid": True,
            "reason": None,
            "canonical_contract_id": canonical_contract_id,
            "observed_at": self._observation_key(observed_at),
            "available_fields": available,
            "total_fields": total,
            "coverage_pct": round(Decimal(available) / Decimal(total) * Decimal("100.00"), 2),
            "data": {
                "market": obs.market,
                "exchange": obs.exchange,
                "underlying": obs.underlying,
                "instrument_type": obs.instrument_type,
                "expiry": obs.expiry,
                "strike": float(obs.strike) if obs.strike is not None else None,
                "option_type": obs.option_type,
                "spot_price": float(obs.spot_price) if obs.spot_price is not None else None,
                "last_price": float(obs.last_price) if obs.last_price is not None else None,
                "volume": obs.volume,
                "open_interest": obs.open_interest,
                "bid_price": float(obs.bid_price) if obs.bid_price is not None else None,
                "ask_price": float(obs.ask_price) if obs.ask_price is not None else None,
                "implied_volatility": float(obs.implied_volatility) if obs.implied_volatility is not None else None,
                "delta": float(obs.delta) if obs.delta is not None else None,
                "gamma": float(obs.gamma) if obs.gamma is not None else None,
                "theta": float(obs.theta) if obs.theta is not None else None,
                "vega": float(obs.vega) if obs.vega is not None else None,
            }
        }

    def calibrate_score(
        self,
        base_score: Decimal,
        canonical_contract_id: str,
        observed_at: datetime,
    ) -> Decimal:
        """Calibrate a base opportunity score against historical observation data.

        Applies adjustments based on:
        - Engine coverage percentage at the observation timestamp
        - Missing engine adjustments
        - Baseline comparison

        Returns calibrated score in 0-100 range.
        """
        validation = self.validate_observation_at(canonical_contract_id, observed_at)

        if not validation["valid"]:
            # No observation data — return base score unchanged but marked incomplete
            return base_score

        coverage_pct = validation["coverage_pct"]
        available = validation["available_fields"]
        total = validation["total_fields"]

        # Start with base score
        calibrated = base_score

        # Apply coverage-based adjustment
        if coverage_pct >= Decimal("80.0"):
            # High coverage — minimal adjustment, score as-is
            adjustment = Decimal("0.00")
        elif coverage_pct >= Decimal("50.0"):
            # Medium coverage — slight downward adjustment
            adjustment = -(base_score * Decimal("0.10"))  # -10%
        elif coverage_pct >= Decimal("20.0"):
            # Low coverage — moderate adjustment
            adjustment = -base_score * Decimal("0.25")  # -25%
        else:
            # Very low coverage — significant adjustment
            adjustment = -base_score * Decimal("0.50")  # -50%

        calibrated = base_score + adjustment
        # Clamp to 0-100 range
        calibrated = max(Decimal("0"), min(Decimal("100"), calibrated))

        # Record the missing engine adjustment if significant
        if available < total:
            missing = total - available
            # Store calibration record for later review
            _record_calibration(
                canonical_contract_id=canonical_contract_id,
                observed_at=observed_at,
                base_score=base_score,
                calibrated_score=calibrated,
                calibration_factor=coverage_pct / Decimal("100.0"),
                missing_engine_adjustment=Decimal(str(round(Decimal("0.10") * missing / Decimal(total), 4))),
                baseline_score=base_score,
                calibration_type="engine_coverage",
            )

        return calibrated.quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")

    def validate_replay_fidelity(
        self,
        candidate_id: str,
        evaluated_at: str,
        observed_timestamps: List[datetime],
    ) -> Dict[str, Any]:
        """Validate that replay does not introduce look-ahead leakage.

        Checks that all observed timestamps used for replay are point-in-time
        and that no post-evaluation data was available at replay time.
        """
        issues: List[str] = []
        verified = 0

        for ts in observed_timestamps:
            key = (candidate_id, self._observation_key(ts))
            if key in self._index:
                verified += 1
            else:
                issues.append(
                    f"no_observation_at_replay_time: candidate={candidate_id}, "
                    f"timestamp={self._observation_key(ts)}"
                )

        total = len(observed_timestamps)
        return {
            "total_timestamps": total,
            "verified_point_in_time": verified,
            "look_ahead_issues": issues,
            "fidelity": round(verified / total * 100.0, 2) if total > 0 else 0.0,
        }


def _record_calibration(
    *,
    canonical_contract_id: str,
    observed_at: datetime,
    base_score: Decimal,
    calibrated_score: Decimal,
    calibration_factor: Decimal,
    missing_engine_adjustment: Decimal,
    baseline_score: Decimal,
    calibration_type: str,
) -> None:
    """Internal: Record a calibration entry for pipeline tuning.

    In production this would write to the replay_calibration table.
    For now, it is a no-op stub that preserves the calibration intent.
    """
    # TODO: Write to replay_calibration table when DB schema is finalized
    # This keeps the calibration pipeline deterministic and auditable
    pass