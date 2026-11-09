"""Unit tests for V2.10A Historical Observation & Replay Foundation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.analysis.models import HistoricalObservationModel
from app.analysis.replay import ReplayContext
from app.discovery.scanner import MarketCandidate, ReferenceTestScanner, ScannerContext
from app.discovery.provider import OptionChainSnapshot, NormalizedOptionContract
from app.analysis.engine import AnalysisContext
from app.analysis.engines import LiquidityQualityEngine


@pytest.fixture
def replay_db(tmp_path):
    db_path = tmp_path / "replay_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine


def _utc(dt: datetime) -> datetime:
    """Normalize any datetime to naive UTC for SQLite compatibility."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _observation_key(observed_at: datetime) -> str:
    """Normalize observed_at to a consistent ISO string for indexing.

    Strips timezone info so that naive (SQLite) and aware (Python datetime)
    datetimes produce the same key. This is critical because SQLite returns
    naive datetimes even when the column is defined with timezone=True.
    """
    if observed_at.tzinfo is not None:
        observed_at = observed_at.replace(tzinfo=None)
    return observed_at.isoformat()


def test_missing_vs_zero_preservation():
    """Verify missing fields (NULL) are strictly distinguished from zero (0)."""
    obs = HistoricalObservationModel(
        canonical_contract_id="TEST:NFO:OPT",
        observed_at=_utc(datetime.now()),
        market="INDIA",
        exchange="NFO",
        underlying="NIFTY",
        instrument_type="OPTION",
        implied_volatility=None,  # Missing IV
        delta=None,               # Missing Delta
        open_interest=None,       # Missing OI
        last_price=Decimal("100"),
    )

    assert obs.implied_volatility is None
    assert obs.delta is None
    assert obs.open_interest is None


def test_persist_and_retrieve_fidelity(replay_db):
    t0 = _utc(datetime(2026, 11, 9, 10, 0, 0))
    with Session(replay_db) as session:
        obs = HistoricalObservationModel(
            canonical_contract_id="NIFTY:NFO:NIFTY26NOV23P24000:OPTION",
            observed_at=t0,
            market="INDIA",
            exchange="NFO",
            underlying="NIFTY",
            instrument_type="OPTION",
            expiry="2026-11-26",
            strike=Decimal("24000"),
            option_type="PUT",
            spot_price=Decimal("24050.0"),
            last_price=Decimal("150.0"),
            volume=5000,
            open_interest=12000,
            bid_price=Decimal("149.0"),
            ask_price=Decimal("151.0"),
            implied_volatility=None,  # Missing IV
            delta=Decimal("-0.45"),
            provider="fixture",
        )
        session.add(obs)
        session.commit()

        # Retrieve
        retrieved = session.query(HistoricalObservationModel).filter_by(
            canonical_contract_id="NIFTY:NFO:NIFTY26NOV23P24000:OPTION",
        ).first()

        assert retrieved is not None
        assert retrieved.canonical_contract_id == obs.canonical_contract_id
        assert retrieved.implied_volatility is None
        assert retrieved.delta == Decimal("-0.45")
        # Normalize: SQLite returns naive; normalize both to naive for comparison
        assert retrieved.observed_at.replace(tzinfo=None) == t0.replace(tzinfo=None)


def test_replay_context_reconstruction_and_scanner_integration(replay_db):
    t0 = _utc(datetime(2026, 11, 9, 10, 0, 0))
    t1 = _utc(datetime(2026, 11, 9, 11, 0, 0))

    with Session(replay_db) as session:
        obs_t0 = HistoricalObservationModel(
            canonical_contract_id="NIFTY:NFO:NIFTY26NOV23P24000:OPTION",
            observed_at=t0,
            market="INDIA",
            exchange="NFO",
            underlying="NIFTY",
            instrument_type="OPTION",
            expiry="2026-11-26",
            strike=Decimal("24000"),
            option_type="PUT",
            spot_price=Decimal("24050.0"),
            last_price=Decimal("150.0"),
            volume=5000,
            open_interest=12000,
            bid_price=Decimal("149.0"),
            ask_price=Decimal("151.0"),
            implied_volatility=Decimal("15.5"),
            delta=Decimal("-0.45"),
            provider="fixture",
        )
        obs_t1 = HistoricalObservationModel(
            canonical_contract_id="NIFTY:NFO:NIFTY26NOV23P24000:OPTION",
            observed_at=t1,
            market="INDIA",
            exchange="NFO",
            underlying="NIFTY",
            instrument_type="OPTION",
            expiry="2026-11-26",
            strike=Decimal("24000"),
            option_type="PUT",
            spot_price=Decimal("24100.0"),
            last_price=Decimal("160.0"),
            volume=6000,
            open_interest=13000,
            bid_price=Decimal("159.0"),
            ask_price=Decimal("161.0"),
            implied_volatility=Decimal("16.0"),
            delta=Decimal("-0.50"),
            provider="fixture",
        )
        session.add_all([obs_t0, obs_t1])
        session.commit()

        all_obs = session.query(HistoricalObservationModel).all()
        context = ReplayContext(all_obs)

        # Replay at t0 should have last_price 150
        contract_t0 = context.get_normalized_observation("NIFTY:NFO:NIFTY26NOV23P24000:OPTION", t0)
        assert contract_t0.last_price == Decimal("150.0")

        # Replay at t1 should have last_price 160 (point-in-time isolation, no look-ahead)
        contract_t1 = context.get_normalized_observation("NIFTY:NFO:NIFTY26NOV23P24000:OPTION", t1)
        assert contract_t1.last_price == Decimal("160.0")

        # Feed replayed data into scanner / analysis pipeline
        snapshot_t0 = OptionChainSnapshot(
            underlying="NIFTY",
            spot_price=Decimal("24050.0"),
            expiry="2026-11-26",
            provider="replay",
            timestamp=t0,
            contracts=[contract_t0],
        )
        scanner_ctx = ScannerContext(universe_name="replay", snapshot=snapshot_t0, as_of=t0)
        scanner = ReferenceTestScanner()
        candidates = scanner.scan(scanner_ctx)
        assert len(candidates) == 1

        # Run analysis on replayed candidate
        analysis_ctx = AnalysisContext(
            candidate=candidates[0],
            spot_price=snapshot_t0.spot_price,
            expiry=snapshot_t0.expiry,
            strike=contract_t0.strike,
            option_type=contract_t0.option_type,
        )
        lq_engine = LiquidityQualityEngine()
        result = lq_engine.analyze(analysis_ctx)
        assert result.qualifying is True


def test_zero_execution_dependency():
    """Verify replay module maintains zero execution/broker/paper imports."""
    import ast
    from app.analysis import replay

    mod_file = replay.__file__
    forbidden_modules = {
        "paper_trading",
        "broker",
        "execution",
        "order",
        "position",
        "signal",
        "app.paper_trading",
        "app.broker",
    }

    with open(mod_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=mod_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert forbidden not in alias.name, (
                            f"Forbidden import '{alias.name}' found in {mod_file}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_modules:
                        assert forbidden not in node.module, (
                            f"Forbidden import from '{node.module}' found in {mod_file}"
                        )