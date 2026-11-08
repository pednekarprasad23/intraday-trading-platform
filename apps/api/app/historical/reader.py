"""Verified, bounded catalog reads. Missing sessions are never inferred as holidays."""

import hashlib
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.historical.importer import MAX_BYTES, MAX_ROWS, SCHEMA
from app.models import (
    HistoricalGap,
    HistoricalImportJob,
    HistoricalPartition,
    Instrument,
    ProviderSymbol,
)
from app.strategies.contracts import Candle, Source

IST = ZoneInfo("Asia/Kolkata")
MAX_SESSIONS = 100


def _long_path(path):
    """Convert a path to a Windows long path if needed (bypasses MAX_PATH=260 limit)."""
    if sys.platform == "win32":
        return "\\\\?\\" + str(path).replace("/", "\\")
    return str(path)


@dataclass(frozen=True)
class VerifiedSession:
    source: Source
    bars: tuple[Candle, ...]
    underlying_id: UUID
    strike_price: Decimal
    session_end: datetime


def _utc(stamp: datetime) -> datetime:
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        # SQLite drops timezone information; catalog timestamps are stored as UTC.
        return stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def read_sessions(
    db: Session,
    root: Path | str,
    *,
    provider: str,
    instrument_id: UUID,
    timeframe: str,
    dates: tuple[date, ...],
) -> tuple[VerifiedSession, ...]:
    """Require an explicit list of sessions; fail closed on any missing or damaged partition."""
    if (
        not provider
        or timeframe not in {"1m", "5m"}
        or not dates
        or len(dates) > MAX_SESSIONS
    ):
        raise ValueError("Provider, timeframe and 1..100 explicit dates required")
    if len(set(dates)) != len(dates) or tuple(sorted(dates)) != dates:
        raise ValueError("Session dates must be unique and chronological")
    instrument = db.get(Instrument, instrument_id)
    if (
        instrument is None
        or instrument.asset_class != "OPTION"
        or instrument.underlying_id is None
        or instrument.expiry_date is None
        or instrument.strike_price is None
        or not instrument.strike_price.is_finite()
        or instrument.strike_price <= 0
        or instrument.option_type not in {"CE", "PE"}
        or instrument.metadata_source in {"ROLLING", "RELATIVE_STRIKE"}
    ):
        raise ValueError("Exact option contract metadata required (no rolling series)")
    mappings = db.scalars(
        select(ProviderSymbol).where(
            ProviderSymbol.instrument_id == instrument_id,
            ProviderSymbol.provider == provider,
        )
    ).all()
    if len(mappings) != 1:
        raise ValueError("Exactly one provider mapping required")
    mapping = mappings[0]
    # Convert to Path and resolve - handle Windows long paths
    root = Path(root) if isinstance(root, str) else root
    root = root.resolve(strict=True)
    result = []
    for day in dates:
        if day > instrument.expiry_date:
            raise ValueError("Contract expired before requested session")
        partitions = db.scalars(
            select(HistoricalPartition).where(
                HistoricalPartition.provider == provider,
                HistoricalPartition.instrument_id == instrument_id,
                HistoricalPartition.timeframe == timeframe,
                HistoricalPartition.session_date == day,
            )
        ).all()
        if len(partitions) != 1:
            raise ValueError(f"Missing or ambiguous catalog session: {day}")
        part = partitions[0]
        job = db.get(HistoricalImportJob, part.job_id)
        if (
            job is None
            or job.status != "COMPLETED"
            or job.schema_version != 1
            or job.provider != provider
            or job.instrument_id != instrument_id
            or job.provider_instrument_key != mapping.provider_instrument_key
            or job.timeframe != timeframe
            or job.session_date != day
            or job.row_count != part.row_count
            or not 0 < part.row_count <= MAX_ROWS
            or job.gap_count != 0
            or db.scalar(select(HistoricalGap.id).where(HistoricalGap.job_id == job.id))
            is not None
        ):
            raise ValueError("Incomplete or inconsistent catalog / cataloged gaps")
        start, end = _utc(job.requested_from), _utc(job.requested_to)
        step = timedelta(minutes=int(timeframe[0]))
        if (
            start.astimezone(IST).date() != day
            or end.astimezone(IST).date() != day
            or end <= start
            or (end - start) != step * part.row_count
        ):
            raise ValueError("Session window / coverage mismatch")
        if mapping.valid_from and start < _utc(mapping.valid_from):
            raise ValueError("Mapping not valid at session start")
        if mapping.valid_to and end > _utc(mapping.valid_to):
            raise ValueError("Mapping not valid through session end")
        expected = (
            Path(f"provider={provider}")
            / f"timeframe={timeframe}"
            / f"session_date={day.isoformat()}"
            / f"instrument_id={instrument_id}"
            / f"{part.checksum_sha256}.parquet"
        )
        if (
            len(part.checksum_sha256) != 64
            or any(c not in "0123456789abcdef" for c in part.checksum_sha256)
            or part.relative_path != expected.as_posix()
        ):
            raise ValueError("Partition path or checksum identity mismatch")
        target = root / expected

        # On Windows, use long path prefix for file operations to bypass MAX_PATH=260 limit
        if sys.platform == "win32":
            target_str = _long_path(target)
            # Check file exists and get size using the path directly
            import os
            if not os.path.isfile(target_str) or os.path.getsize(target_str) > MAX_BYTES:
                raise ValueError("Unsafe, missing or oversized partition")
            # Use long path for reading
            with open(target_str, "rb") as fh:
                raw = fh.read()
        else:
            if (
                not target.is_file()
                or target.is_symlink()
                or target.resolve() != root / expected
                or not target.resolve().is_relative_to(root)
                or target.stat().st_size > MAX_BYTES
            ):
                raise ValueError("Unsafe, missing or oversized partition")
            raw = target.read_bytes()
        if hashlib.sha256(raw).hexdigest() != part.checksum_sha256:
            raise ValueError("Partition checksum mismatch")
        try:
            parquet = pq.ParquetFile(BytesIO(raw))
            if (
                parquet.schema_arrow != SCHEMA
                or parquet.metadata.num_rows != part.row_count
            ):
                raise ValueError("Partition schema or row count mismatch")
            table = parquet.read()
            rows = table.to_pylist()
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError("Unreadable Parquet partition") from exc
        bars = tuple(
            Candle(
                row["bar_time"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
            )
            for row in rows
        )
        if any(bar.bar_time != start + step * index for index, bar in enumerate(bars)):
            raise ValueError("Non-UTC, unordered or missing bars in partition")
        if (
            _utc(job.observed_from) != bars[0].bar_time
            or _utc(job.observed_to) != bars[-1].bar_time
        ):
            raise ValueError("Observed catalog range mismatch")
        source = Source(
            instrument_id,
            provider,
            mapping.provider_instrument_key,
            part.id,
            part.checksum_sha256,
            job.source_sha256,
            day,
            timeframe,
            instrument.expiry_date,
            instrument.option_type,
        )
        result.append(
            VerifiedSession(
                source, bars, instrument.underlying_id, instrument.strike_price, end
            )
        )
    return tuple(result)
