from datetime import date, time
from hashlib import sha256
from pathlib import Path
from decimal import Decimal

import pyarrow.parquet as pq
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.historical.importer import _parse, import_fixture, orphan_files
from app.models import (
    Base,
    Instrument,
    ProviderSymbol,
    HistoricalGap,
    HistoricalImportJob,
    HistoricalPartition,
)


def setup_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'historical.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        instrument = Instrument(
            canonical_symbol="DEMO:OPTION:100CE",
            display_name="Synthetic option",
            asset_class="OPTION",
            exchange="DEMO",
            segment="DEMO",
            expiry_date=date(2030, 12, 31),
            strike_price=Decimal("100"),
            option_type="CE",
        )
        db.add(instrument)
        db.flush()
        db.add(
            ProviderSymbol(
                instrument_id=instrument.id,
                provider="DEMO",
                provider_instrument_key="OPT100CE",
            )
        )
        db.commit()
        return engine, instrument.id


def test_import_deduplicates_reports_gaps_and_is_idempotent(tmp_path):
    engine, _ = setup_db(tmp_path)
    fixture = Path(__file__).parent / "fixtures" / "DEMO_option_1m.csv"
    digest = sha256(fixture.read_bytes()).hexdigest()
    root = tmp_path / "parquet"
    with Session(engine) as db:
        job = import_fixture(
            db,
            fixture,
            root,
            provider="DEMO",
            provider_key="OPT100CE",
            timeframe="1m",
            session_date=date(2026, 11, 6),
            session_start=time(9, 15),
            session_end=time(9, 18),
            source_sha256=digest,
        )
        db.commit()
        assert (job.row_count, job.duplicate_count, job.gap_count) == (2, 1, 1)
        partition = db.scalar(select(HistoricalPartition))
        assert (
            partition
            and pq.ParquetFile(root / partition.relative_path).metadata.num_rows == 2
        )
        assert db.scalar(select(HistoricalGap)) is not None
        assert (
            sha256((root / partition.relative_path).read_bytes()).hexdigest()
            == partition.checksum_sha256
        )
        assert len(db.scalars(select(HistoricalImportJob)).all()) == 1
        instrument = db.get(Instrument, partition.instrument_id)
        mapping = db.scalar(select(ProviderSymbol))
        assert (
            instrument.data_available is False and instrument.execution_enabled is False
        )
        assert mapping.data_enabled is False and mapping.execution_enabled is False
        again = import_fixture(
            db,
            fixture,
            root,
            provider="DEMO",
            provider_key="OPT100CE",
            timeframe="1m",
            session_date=date(2026, 11, 6),
            session_start=time(9, 15),
            session_end=time(9, 18),
            source_sha256=digest,
        )
        assert again.id == job.id
        assert len(list(root.rglob("*.parquet"))) == 1


def test_rejects_conflicting_duplicate_and_unmapped(tmp_path):
    engine, _ = setup_db(tmp_path)
    fixture = tmp_path / "conflict.csv"
    fixture.write_text(
        "bar_time,open,high,low,close,volume\n2026-11-06T09:15:00+05:30,10,10,9,10,1\n2026-11-06T09:15:00+05:30,10,11,9,10,1\n",
        encoding="utf-8",
    )
    with Session(engine) as db:
        with pytest.raises(ValueError, match="Conflicting"):
            import_fixture(
                db,
                fixture,
                tmp_path / "parquet",
                provider="DEMO",
                provider_key="OPT100CE",
                timeframe="1m",
                session_date=date(2026, 11, 6),
                session_start=time(9, 15),
                session_end=time(9, 16),
                source_sha256=sha256(fixture.read_bytes()).hexdigest(),
            )
        with pytest.raises(ValueError, match="mapping"):
            import_fixture(
                db,
                fixture,
                tmp_path / "parquet",
                provider="DEMO",
                provider_key="UNKNOWN",
                timeframe="1m",
                session_date=date(2026, 11, 6),
                session_start=time(9, 15),
                session_end=time(9, 16),
                source_sha256=sha256(fixture.read_bytes()).hexdigest(),
            )


def test_5m_ist_alignment_and_invalid_values():
    fixture = Path(__file__).parent / "fixtures" / "DEMO_option_5m.csv"
    rows, duplicates, gaps, start, end = _parse(
        fixture.read_bytes(), date(2026, 11, 6), time(9, 15), time(9, 25), 5
    )
    assert len(rows) == 2 and not duplicates and not gaps
    assert start.isoformat() == "2026-11-06T03:45:00+00:00"
    assert end.isoformat() == "2026-11-06T03:55:00+00:00"
    invalid = (
        b"bar_time,open,high,low,close,volume\n2026-11-06T09:15:00,10,10,9,10,-1\n"
    )
    with pytest.raises(ValueError, match="timezone"):
        _parse(invalid, date(2026, 11, 6), time(9, 15), time(9, 20), 5)


def test_orphan_diagnostic_does_not_delete(tmp_path):
    root = tmp_path / "parquet"
    root.mkdir()
    (root / "orphan.parquet").write_bytes(b"not cataloged")
    assert orphan_files(root, set()) == ["orphan.parquet"]
    assert (root / "orphan.parquet").exists()
