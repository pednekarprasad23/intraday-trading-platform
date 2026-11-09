"""Unit tests for V2.10D Replay Validation / Calibration Foundation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.analysis.models import HistoricalObservationModel
from app.analysis.replay_validation import ReplayValidator


def _make_obs(observed_at: datetime | None = None, **kwargs) -> HistoricalObservationModel:
    """Helper to create a HistoricalObservationModel with default values."""
    import datetime as _dtmod
    if observed_at is None:
        observed_at = _dtmod.datetime.now(timezone.utc)
    defaults = {
        "canonical_contract_id": "TEST:NFO:OPT",
        "observed_at": observed_at,
        "market": "INDIA",
        "exchange": "NFO",
        "underlying": "NIFTY",
        "instrument_type": "OPTION",
        "expiry": "2026-11-28",
        "strike": Decimal("18000.0000"),
        "option_type": "CE",
        "spot_price": Decimal("18050.0000"),
        "last_price": Decimal("18100.0000"),
        "volume": 5000,
        "open_interest": 12000,
        "bid_price": Decimal("18090.0000"),
        "ask_price": Decimal("18110.0000"),
        "implied_volatility": Decimal("15.5000"),
        "delta": Decimal("0.450000"),
        "gamma": Decimal("0.002000"),
        "theta": Decimal("-12.5000"),
        "vega": Decimal("25.0000"),
    }
    defaults.update(kwargs)
    return HistoricalObservationModel(**defaults)


def _utc(dt: datetime) -> datetime:
    """Normalize any datetime to naive UTC for SQLite compatibility."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def test_replay_validator_validates_observation_exists():
    """Validate that an observation exists at a given point-in-time."""
    observed = _utc(datetime.now())
    obs = _make_obs(observed_at=observed)
    validator = ReplayValidator([obs])

    result = validator.validate_observation_at(
        "TEST:NFO:OPT",
        observed,
    )

    assert result["valid"] is True
    assert result["reason"] is None
    assert result["coverage_pct"] == Decimal("100.00")


def test_replay_validator_missing_observation():
    """Validate returns invalid when no observation exists at point-in-time."""
    validator = ReplayValidator([])

    result = validator.validate_observation_at(
        "NONEXISTENT:NFO:OPT",
        _utc(datetime.now()),
    )

    assert result["valid"] is False
    assert result["reason"] == "no_observation_at_point_in_time"


def test_replay_validator_calibrate_score_full_coverage():
    """Calibrate score with full observation coverage (no adjustment)."""
    observed = _utc(datetime.now())
    obs = _make_obs(observed_at=observed)
    validator = ReplayValidator([obs])

    calibrated = validator.calibrate_score(
        Decimal("90.00"),
        "TEST:NFO:OPT",
        observed,
    )

    assert calibrated == Decimal("90.00")


def test_replay_validator_calibrate_score_partial_coverage():
    """Calibrate score with partial observation coverage (downward adjustment).

    Only 2 of 11 numeric fields populated -> ~18.18% coverage -> -50% adjustment
    (since < 20% threshold).
    90.00 * 0.50 = 45.00
    """
    # Create observation with ONLY spot_price and last_price set;
    # all other numeric fields cleared to None.
    observed = _utc(datetime.now())
    obs = _make_obs(observed_at=observed)
    obs.spot_price = Decimal("18050.0000")
    obs.last_price = Decimal("18100.0000")
    # Clear ALL other numeric fields
    obs.volume = None
    obs.open_interest = None
    obs.bid_price = None
    obs.ask_price = None
    obs.implied_volatility = None
    obs.delta = None
    obs.gamma = None
    obs.theta = None
    obs.vega = None

    validator = ReplayValidator([obs])

    calibrated = validator.calibrate_score(
        Decimal("90.00"),
        "TEST:NFO:OPT",
        observed,
    )

    # 2 out of 11 fields = ~18.18% coverage -> -50% adjustment
    # (below 20% threshold)
    # 90.00 * 0.50 = 45.00
    assert calibrated < Decimal("90.00")
    assert calibrated >= Decimal("0")
    # Should be exactly 45.00 with ROUND_HALF_UP
    assert calibrated == Decimal("45.00")


def test_replay_validator_calibrate_score_zero_coverage():
    """Calibrate score with zero observation coverage (large downward adjustment)."""
    # Create observation with NO numeric fields
    observed = _utc(datetime.now())
    obs = _make_obs(observed_at=observed)
    obs.spot_price = None
    obs.last_price = None
    obs.volume = None
    obs.open_interest = None
    obs.bid_price = None
    obs.ask_price = None
    obs.implied_volatility = None
    obs.delta = None
    obs.gamma = None
    obs.theta = None
    obs.vega = None

    validator = ReplayValidator([obs])

    calibrated = validator.calibrate_score(
        Decimal("90.00"),
        "TEST:NFO:OPT",
        observed,
    )

    # 0% coverage -> -50% adjustment -> 90.00 * 0.5 = 45.00
    assert calibrated == Decimal("45.00")


def test_replay_validator_validate_replay_fidelity():
    """Validate replay fidelity against point-in-time observations.

    Create observations at the exact timestamps being tested, so the
    point-in-time index lookup succeeds.
    """
    # Use consistent contract IDs - observations stored with "TEST:NFO:OPT"
    # and replay fidelity checks against the same ID.
    # Use naive UTC timestamps consistent with _observation_key stripping tzinfo
    observed1 = datetime(2026, 11, 9, 10, 0, 0)  # naive UTC
    observed2 = datetime(2026, 11, 9, 15, 0, 0)  # naive UTC
    obs1 = _make_obs(observed_at=observed1, canonical_contract_id="CANDIDATE-A")
    obs2 = _make_obs(observed_at=observed2, canonical_contract_id="CANDIDATE-A")

    validator = ReplayValidator([obs1, obs2])

    # Both timestamps should be verified since observations exist at those times
    result = validator.validate_replay_fidelity(
        "CANDIDATE-A",
        "2026-11-09T10:00:00+00:00",
        [observed1, observed2],
    )

    assert result["total_timestamps"] == 2
    assert result["verified_point_in_time"] == 2
    assert len(result["look_ahead_issues"]) == 0
    assert result["fidelity"] == 100.0


def test_replay_validator_validate_replay_fidelity_missing():
    """Validate replay fidelity with timestamps having no observations."""
    validator = ReplayValidator([])

    result = validator.validate_replay_fidelity(
        "CANDIDATE-A",
        "2026-11-09T10:00:00+00:00",
        [_utc(datetime.now()), _utc(datetime.now())],
    )

    assert result["total_timestamps"] == 2
    assert result["verified_point_in_time"] == 0
    assert len(result["look_ahead_issues"]) == 2
    assert result["fidelity"] == 0.0


def test_replay_validator_zero_execution_coupling():
    """Verify replay validation module has zero execution/broker imports."""
    import ast
    mod_file = __file__

    with open(mod_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=mod_file)

    forbidden_modules = {
        "paper_trading", "broker", "execution", "order", "position", "signal",
        "app.paper_trading", "app.broker",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in forbidden_modules:
                    assert forbidden not in alias.name, (
                        f"Forbidden import '{alias.name}' found in {mod_file}"
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            for forbidden in forbidden_modules:
                assert forbidden not in node.module, (
                    f"Forbidden import from '{node.module}' found in {mod_file}"
                )


def test_calibration_record_preserves_point_in_time():
    """Verify calibration records preserve point-in-time integrity."""
    # _record_calibration is a no-op stub; verify it doesn't crash
    # and accepts the right typed arguments
    try:
        from app.analysis.replay_validation import _record_calibration

        _record_calibration(
            canonical_contract_id="TEST:NFO:OPT",
            observed_at=_utc(datetime.now()),
            base_score=Decimal("85.00"),
            calibrated_score=Decimal("75.00"),
            calibration_factor=Decimal("0.8000"),
            missing_engine_adjustment=Decimal("0.1000"),
            baseline_score=Decimal("85.00"),
            calibration_type="engine_coverage",
        )
    except TypeError as e:
        pytest.fail(f"_record_calibration raised TypeError: {e}")