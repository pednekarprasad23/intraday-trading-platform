"""Bounded CSV fixture -> validated, immutable Parquet; no provider network access."""

import csv
import hashlib
import io
import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    HistoricalGap,
    HistoricalImportJob,
    HistoricalPartition,
    Instrument,
    ProviderSymbol,
)

IST = ZoneInfo("Asia/Kolkata")
COLUMNS = ["bar_time", "open", "high", "low", "close", "volume"]
SCHEMA = pa.schema(
    [
        ("bar_time", pa.timestamp("us", tz="UTC")),
        ("open", pa.decimal128(18, 4)),
        ("high", pa.decimal128(18, 4)),
        ("low", pa.decimal128(18, 4)),
        ("close", pa.decimal128(18, 4)),
        ("volume", pa.decimal128(20, 4)),
    ]
)
MAX_BYTES = 5_000_000
MAX_ROWS = 50_000


def _decimal(value: str, *, positive: bool = True, precision: int = 18) -> Decimal:
    try:
        result = Decimal(value)
        if not result.is_finite() or (result <= 0 if positive else result < 0):
            raise ValueError("Invalid price or volume")
        if (
            result.as_tuple().exponent < -4
            or len(result.as_tuple().digits) + max(result.as_tuple().exponent, 0)
            > precision
            or result >= Decimal(10) ** (precision - 4)
        ):
            raise ValueError("Price or volume exceeds schema precision")
        return result
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid price or volume") from exc


def _parse(raw: bytes, session_date: date, start: time, end: time, minutes: int):
    try:
        reader = csv.DictReader(
            io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True
        )
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"CSV columns must be {COLUMNS}")
        opened = datetime.combine(session_date, start, IST)
        closed = datetime.combine(session_date, end, IST)
        if (
            start.tzinfo is not None
            or end.tzinfo is not None
            or start.second
            or start.microsecond
            or end.second
            or end.microsecond
            or closed <= opened
            or (closed - opened).total_seconds() % (minutes * 60)
        ):
            raise ValueError("Invalid session window")
        expected = int((closed - opened).total_seconds() // (minutes * 60))
        if expected > MAX_ROWS:
            raise ValueError("Session exceeds row limit")
        bars = {}
        duplicates = 0
        for index, record in enumerate(reader, 1):
            if index > MAX_ROWS:
                raise ValueError("Fixture exceeds row limit")
            if None in record or any(v is None for v in record.values()):
                raise ValueError(f"Malformed CSV row {index}")
            try:
                timestamp = datetime.fromisoformat(
                    record["bar_time"].replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise ValueError(f"Invalid timestamp on row {index}") from exc
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("Bar timestamps must have an explicit timezone")
            local = timestamp.astimezone(IST)
            if not opened <= local < closed or (local - opened).total_seconds() % (
                minutes * 60
            ):
                raise ValueError(f"Bar outside session or not aligned on row {index}")
            values = tuple(
                _decimal(
                    record[key],
                    positive=key != "volume",
                    precision=20 if key == "volume" else 18,
                )
                for key in COLUMNS[1:]
            )
            opening, high, low, closing, _ = values
            if (
                low > min(opening, closing)
                or high < max(opening, closing)
                or high < low
            ):
                raise ValueError(f"Invalid OHLC on row {index}")
            utc = local.astimezone(timezone.utc)
            if utc in bars:
                if bars[utc] != values:
                    raise ValueError(f"Conflicting bar at {utc.isoformat()}")
                duplicates += 1
            else:
                bars[utc] = values
        if not bars:
            raise ValueError("Empty fixture")
        ordered = sorted(bars.items())
        gaps = [
            (opened + timedelta(minutes=minutes * n)).astimezone(timezone.utc)
            for n in range(expected)
            if (opened + timedelta(minutes=minutes * n)).astimezone(timezone.utc)
            not in bars
        ]
        return (
            ordered,
            duplicates,
            gaps,
            opened.astimezone(timezone.utc),
            closed.astimezone(timezone.utc),
        )
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("Invalid CSV fixture") from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _table(rows):
    return pa.Table.from_arrays(
        [pa.array([stamp for stamp, _ in rows], type=SCHEMA.field(0).type)]
        + [
            pa.array([values[i] for _, values in rows], type=SCHEMA.field(i + 1).type)
            for i in range(5)
        ],
        schema=SCHEMA,
    )


def import_fixture(
    db: Session,
    path: Path,
    root: Path,
    *,
    provider: str,
    provider_key: str,
    timeframe: str,
    session_date: date,
    session_start: time,
    session_end: time,
    source_sha256: str,
) -> HistoricalImportJob:
    """One explicit trading session per fixture. Caller owns the DB transaction."""
    if timeframe not in {"1m", "5m"} or not provider or not provider_key:
        raise ValueError("Explicit provider, key and 1m/5m timeframe required")
    if not provider.isascii() or not all(c.isalnum() or c in "_-" for c in provider):
        raise ValueError("Invalid provider identity")
    if (
        len(provider) > 50
        or len(provider_key) > 200
        or any(ord(c) < 32 for c in provider_key)
    ):
        raise ValueError("Invalid provider identity")
    if len(source_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in source_sha256
    ):
        raise ValueError("Explicit lowercase SHA-256 required")
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Fixture missing or exceeds byte limit")
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES or _sha256(raw) != source_sha256:
        raise ValueError("Fixture SHA-256 mismatch or byte limit exceeded")
    mappings = db.scalars(
        select(ProviderSymbol).where(
            ProviderSymbol.provider == provider,
            ProviderSymbol.provider_instrument_key == provider_key,
        )
    ).all()
    if len(mappings) != 1:
        raise ValueError("Unknown or ambiguous provider mapping")
    mapping = mappings[0]
    instrument = db.get(Instrument, mapping.instrument_id)
    if (
        instrument is None
        or instrument.asset_class != "OPTION"
        or instrument.expiry_date is None
        or instrument.strike_price is None
        or instrument.option_type not in {"CE", "PE"}
    ):
        raise ValueError("Verified option metadata required")
    if mapping.valid_from and datetime.combine(
        session_date, session_start, IST
    ).astimezone(timezone.utc) < mapping.valid_from.replace(
        tzinfo=mapping.valid_from.tzinfo or timezone.utc
    ):
        raise ValueError("Provider mapping not valid at session start")
    if mapping.valid_to and datetime.combine(session_date, session_end, IST).astimezone(
        timezone.utc
    ) > mapping.valid_to.replace(tzinfo=mapping.valid_to.tzinfo or timezone.utc):
        raise ValueError("Provider mapping expired within session")
    existing = db.scalar(
        select(HistoricalImportJob).where(
            HistoricalImportJob.provider == provider,
            HistoricalImportJob.instrument_id == instrument.id,
            HistoricalImportJob.timeframe == timeframe,
            HistoricalImportJob.session_date == session_date,
            HistoricalImportJob.source_sha256 == source_sha256,
        )
    )
    if existing:
        expected_from = datetime.combine(session_date, session_start, IST).astimezone(
            timezone.utc
        )
        expected_to = datetime.combine(session_date, session_end, IST).astimezone(
            timezone.utc
        )
        actual_from = existing.requested_from.replace(
            tzinfo=existing.requested_from.tzinfo or timezone.utc
        ).astimezone(timezone.utc)
        actual_to = existing.requested_to.replace(
            tzinfo=existing.requested_to.tzinfo or timezone.utc
        ).astimezone(timezone.utc)
        if (
            existing.provider_instrument_key != provider_key
            or actual_from != expected_from
            or actual_to != expected_to
        ):
            raise ValueError("Existing source has different import parameters")
        if existing.status == "COMPLETED":
            return existing
        raise ValueError("Existing incomplete import requires operator review")
    if db.scalar(
        select(HistoricalPartition).where(
            HistoricalPartition.provider == provider,
            HistoricalPartition.instrument_id == instrument.id,
            HistoricalPartition.timeframe == timeframe,
            HistoricalPartition.session_date == session_date,
        )
    ):
        raise ValueError(
            "Immutable partition already exists; revision requires operator review"
        )
    minutes = int(timeframe[0])
    rows, duplicates, gaps, requested_from, requested_to = _parse(
        raw, session_date, session_start, session_end, minutes
    )
    table = _table(rows)
    relative_dir = (
        Path(f"provider={provider}")
        / f"timeframe={timeframe}"
        / f"session_date={session_date.isoformat()}"
        / f"instrument_id={instrument.id}"
    )
    directory = root / relative_dir
    # Create the full directory tree. pathlib.mkdir(parents=True) works
    # reliably on Windows when given a pure Path object.
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    directory.mkdir(parents=True, exist_ok=True)

    staging = directory / f".{uuid4().hex}.staging"
    try:
        # Use the \\?\ prefix for long paths on Windows (MAX_PATH = 260).
        # pathlib Path.open() and open() both fail on long paths without this prefix.
        import sys as _sys
        if _sys.platform == "win32":
            staging_str = "\\\\?\\" + str(staging).replace("/", "\\")
        else:
            staging_str = str(staging)
        # Write parquet
        with open(staging_str, "wb") as fh:
            pq.write_table(table, fh, compression="zstd")
            fh.flush()
            os.fsync(fh.fileno())
        # Readback verification
        with open(staging_str, "rb") as fh:
            readback = pq.ParquetFile(fh).read()
        if (
            readback.schema != SCHEMA
            or readback.num_rows != len(rows)
            or not readback.equals(table)
        ):
            raise ValueError("Parquet readback mismatch")
        checksum = _sha256(open(staging_str, "rb").read())
        final = directory / f"{checksum}.parquet"
        if final.exists():
            raise ValueError("Uncataloged final file exists; operator review required")
        # Exclusive creation avoids silently replacing an uncommitted file from
        # another importer; the staging file is on the same filesystem.
        final_str = "\\\\?\\" + str(final).replace("/", "\\") if _sys.platform == "win32" else str(final)
        os.link(staging_str, final_str)
        Path(staging_str).unlink()
        # fsync directory to ensure rename is durable (skip on Windows — \\?\ paths
        # don't work with os.open for directories there).
        if _sys.platform != "win32":
            directory_fd = os.open(str(directory), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        job = HistoricalImportJob(
            provider=provider,
            provider_instrument_key=provider_key,
            instrument_id=instrument.id,
            timeframe=timeframe,
            session_date=session_date,
            source_sha256=source_sha256,
            requested_from=requested_from,
            requested_to=requested_to,
            observed_from=rows[0][0],
            observed_to=rows[-1][0],
            status="COMPLETED",
            row_count=len(rows),
            duplicate_count=duplicates,
            gap_count=len(gaps),
        )
        db.add(job)
        db.flush()
        db.add(
            HistoricalPartition(
                job_id=job.id,
                provider=provider,
                instrument_id=instrument.id,
                timeframe=timeframe,
                session_date=session_date,
                relative_path=(relative_dir / final.name).as_posix(),
                checksum_sha256=checksum,
                row_count=len(rows),
                # P1-B: Populate instrument metadata at import time
                instrument_canonical_symbol=instrument.canonical_symbol,
                instrument_display_name=instrument.display_name,
                underlying_canonical_symbol=(
                    instrument.underlying.canonical_symbol
                    if instrument.underlying else None
                ),
                option_type=instrument.option_type,
                strike_price=instrument.strike_price,
            )
        )
        db.add_all(HistoricalGap(job_id=job.id, bar_time=gap) for gap in gaps)
        db.flush()
        return job
    finally:
        staging.unlink(missing_ok=True)
        # A published file is intentionally retained if DB commit fails: never silently
        # overwrite it. Reconcile against the catalog before retrying.


def orphan_files(root: Path, catalog_paths: set[str]) -> list[str]:
    """Operator diagnostic; never delete orphaned data automatically."""
    if not root.exists():
        return []
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file()
        and (
            p.name.endswith(".staging")
            or p.relative_to(root).as_posix() not in catalog_paths
        )
    )
