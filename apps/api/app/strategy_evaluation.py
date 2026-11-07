"""Operator-only fixture evaluation boundary. Caller owns the DB transaction."""

import hashlib
import json
from dataclasses import asdict
from datetime import time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.historical.importer import MAX_BYTES, _parse
from app.models import (
    HistoricalImportJob,
    HistoricalPartition,
    Instrument,
    ProviderSymbol,
    StrategySignal,
    StrategyVersion,
)
from app.strategies.contracts import Candle, Source, StrategyConfig
from app.strategies.engine import MAX_BARS, evaluate, validate_config


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
    ).encode("utf-8")


def evaluate_fixture(
    db: Session, fixture: Path, *, job_id, config: StrategyConfig, root: Path
):
    """Revalidate full fixture and immutable catalog identity; reject gaps before persistence."""
    job = db.get(HistoricalImportJob, job_id)
    if job is None or job.status != "COMPLETED":
        raise ValueError("Completed import job required")
    validate_config(config, job.timeframe)
    partitions = db.scalars(
        select(HistoricalPartition).where(HistoricalPartition.job_id == job.id)
    ).all()
    if len(partitions) != 1:
        raise ValueError("Exactly one cataloged partition required")
    partition = partitions[0]
    instrument = db.get(Instrument, job.instrument_id)
    mapping = db.scalar(
        select(ProviderSymbol).where(
            ProviderSymbol.provider == job.provider,
            ProviderSymbol.provider_instrument_key == job.provider_instrument_key,
            ProviderSymbol.instrument_id == job.instrument_id,
        )
    )
    if (
        instrument is None
        or mapping is None
        or instrument.asset_class != "OPTION"
        or instrument.expiry_date is None
        or instrument.option_type not in {"CE", "PE"}
        or instrument.strike_price is None
        or partition.provider != job.provider
        or partition.instrument_id != job.instrument_id
        or partition.timeframe != job.timeframe
        or partition.session_date != job.session_date
    ):
        raise ValueError("Catalog provenance or option metadata mismatch")
    # The partition is immutable but the operator still verifies the on-disk copy.
    # This is a single-file checksum check, not a general catalog reader.
    expected = (
        Path(f"provider={job.provider}")
        / f"timeframe={job.timeframe}"
        / f"session_date={job.session_date.isoformat()}"
        / f"instrument_id={job.instrument_id}"
        / f"{partition.checksum_sha256}.parquet"
    )
    if partition.relative_path != expected.as_posix():
        raise ValueError("Partition path mismatch")
    target = root.resolve() / expected
    if not target.is_file() or target.is_symlink() or target.stat().st_size > MAX_BYTES:
        raise ValueError("Partition missing or exceeds byte limit")
    if hashlib.sha256(target.read_bytes()).hexdigest() != partition.checksum_sha256:
        raise ValueError("Partition checksum mismatch")
    if not fixture.is_file() or fixture.stat().st_size > MAX_BYTES:
        raise ValueError("Fixture missing or too large")
    raw = fixture.read_bytes()
    if hashlib.sha256(raw).hexdigest() != job.source_sha256:
        raise ValueError("Fixture source checksum mismatch")
    start = job.requested_from.replace(
        tzinfo=job.requested_from.tzinfo or timezone.utc
    ).astimezone(ZoneInfo("Asia/Kolkata"))
    end = job.requested_to.replace(
        tzinfo=job.requested_to.tzinfo or timezone.utc
    ).astimezone(ZoneInfo("Asia/Kolkata"))
    if start.date() != job.session_date or end.date() != job.session_date:
        raise ValueError("Import session mismatch")
    rows, duplicates, gaps, _, _ = _parse(
        raw,
        job.session_date,
        time(start.hour, start.minute),
        time(end.hour, end.minute),
        int(job.timeframe[0]),
    )
    if (
        len(rows) != job.row_count
        or len(gaps) != job.gap_count
        or duplicates != job.duplicate_count
        or partition.row_count != len(rows)
    ):
        raise ValueError("Import catalog counts mismatch")
    if gaps:
        raise ValueError("GAP_OR_DUPLICATE: incomplete imported session")
    if len(rows) > MAX_BARS:
        raise ValueError("Window exceeds evaluation limit")
    bars = tuple(Candle(stamp, *values) for stamp, values in rows)
    source = Source(
        instrument.id,
        job.provider,
        job.provider_instrument_key,
        partition.id,
        partition.checksum_sha256,
        job.source_sha256,
        job.session_date,
        job.timeframe,
        instrument.expiry_date,
        instrument.option_type,
    )
    decision = evaluate(config, source, bars)
    if decision.quality != "VALID" or decision.direction == "NONE":
        return decision
    config_data = asdict(config)
    config_digest = hashlib.sha256(canonical(config_data)).hexdigest()
    version = db.scalar(
        select(StrategyVersion).where(
            StrategyVersion.strategy_id == config.strategy_id,
            StrategyVersion.version == config.version,
            StrategyVersion.config_sha256 == config_digest,
        )
    )
    if version is None:
        version = StrategyVersion(
            strategy_id=config.strategy_id,
            version=config.version,
            config_sha256=config_digest,
            config=json.loads(canonical(config_data)),
        )
        db.add(version)
        db.flush()
    snapshot = json.loads(canonical(asdict(decision)))
    digest = hashlib.sha256(canonical(snapshot)).hexdigest()
    existing = db.scalar(
        select(StrategySignal).where(
            StrategySignal.strategy_version_id == version.id,
            StrategySignal.partition_id == partition.id,
            StrategySignal.input_sha256 == digest,
        )
    )
    if existing is None:
        db.add(
            StrategySignal(
                strategy_version_id=version.id,
                instrument_id=instrument.id,
                partition_id=partition.id,
                decision_time=decision.decision_time,
                direction=decision.direction,
                input_sha256=digest,
                snapshot=snapshot,
            )
        )
        db.flush()
    return decision
