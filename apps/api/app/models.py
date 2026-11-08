from datetime import date, datetime, timezone
from decimal import Decimal

from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    canonical_symbol: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    asset_class: Mapped[str] = mapped_column(String(30))
    exchange: Mapped[str] = mapped_column(String(30))
    segment: Mapped[str] = mapped_column(String(50))
    underlying_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("instruments.id"), nullable=True
    )
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    strike_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    option_type: Mapped[str | None] = mapped_column(String(2), nullable=True)
    lot_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    tick_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    data_available: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_source: Mapped[str] = mapped_column(String(100), default="DEMO_FIXTURE")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # P1-B: Relationship to historical partitions
    partitions: Mapped[list["HistoricalPartition"]] = relationship(
        back_populates="instrument"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class ProviderSymbol(Base):
    __tablename__ = "provider_symbols"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_instrument_key", name="uq_provider_symbol"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id"))
    provider: Mapped[str] = mapped_column(String(50))
    provider_instrument_key: Mapped[str] = mapped_column(String(200))
    data_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_exchange: Mapped[str | None] = mapped_column(String(50), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class HistoricalImportJob(Base):
    __tablename__ = "historical_import_jobs"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "instrument_id",
            "timeframe",
            "source_sha256",
            "session_date",
            name="uq_historical_source",
        ),
        CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')", name="ck_historical_status"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(50))
    provider_instrument_key: Mapped[str] = mapped_column(String(200))
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id"))
    timeframe: Mapped[str] = mapped_column(String(2))
    session_date: Mapped[date] = mapped_column(Date)
    source_sha256: Mapped[str] = mapped_column(String(64))
    provider_response_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    provider_retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    schema_version: Mapped[int] = mapped_column(default=1)
    requested_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    row_count: Mapped[int] = mapped_column(default=0)
    duplicate_count: Mapped[int] = mapped_column(default=0)
    reject_count: Mapped[int] = mapped_column(default=0)
    gap_count: Mapped[int] = mapped_column(default=0)
    conflict_count: Mapped[int] = mapped_column(default=0)
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class HistoricalPartition(Base):
    __tablename__ = "historical_partitions"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "instrument_id",
            "timeframe",
            "session_date",
            name="uq_historical_partition",
        ),
        UniqueConstraint("relative_path", name="uq_historical_path"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("historical_import_jobs.id"), unique=True
    )
    provider: Mapped[str] = mapped_column(String(50))
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id"))
    # P1-B: Instrument relationship for metadata access
    instrument: Mapped["Instrument"] = relationship(back_populates="partitions")
    timeframe: Mapped[str] = mapped_column(String(2))
    session_date: Mapped[date] = mapped_column(Date)
    relative_path: Mapped[str] = mapped_column(String(500))
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column()
    # P1-B: Denormalized instrument metadata for quick access
    instrument_canonical_symbol: Mapped[str | None] = mapped_column(String(100), nullable=True)
    instrument_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    underlying_canonical_symbol: Mapped[str | None] = mapped_column(String(100), nullable=True)
    option_type: Mapped[str | None] = mapped_column(String(2), nullable=True)
    strike_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class HistoricalGap(Base):
    __tablename__ = "historical_gaps"
    __table_args__ = (UniqueConstraint("job_id", "bar_time", name="uq_historical_gap"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("historical_import_jobs.id"))
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (
        UniqueConstraint(
            "strategy_id", "version", "config_sha256", name="uq_strategy_config"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    strategy_id: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column()
    config_sha256: Mapped[str] = mapped_column(String(64))
    config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class StrategySignal(Base):
    __tablename__ = "strategy_signals"
    __table_args__ = (
        UniqueConstraint(
            "strategy_version_id",
            "partition_id",
            "input_sha256",
            name="uq_strategy_signal_input",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    strategy_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("strategy_versions.id")
    )
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id"))
    partition_id: Mapped[UUID] = mapped_column(ForeignKey("historical_partitions.id"))
    decision_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    direction: Mapped[str] = mapped_column(String(10))
    input_sha256: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class ResearchEvaluation(Base):
    """Operator-verified decision history; never a broker instruction."""

    __tablename__ = "research_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "partition_id",
            "strategy_config_sha256",
            "input_sha256",
            name="uq_research_evaluation_input",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id"))
    partition_id: Mapped[UUID] = mapped_column(ForeignKey("historical_partitions.id"))
    strategy_id: Mapped[str] = mapped_column(String(100))
    strategy_version: Mapped[int] = mapped_column()
    strategy_config_sha256: Mapped[str] = mapped_column(String(64))
    input_sha256: Mapped[str] = mapped_column(String(64))
    decision_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    direction: Mapped[str] = mapped_column(String(10))
    quality: Mapped[str] = mapped_column(String(20))
    reasons: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class BacktestReport(Base):
    __tablename__ = "backtest_reports"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(50))
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id"))
    timeframe: Mapped[str] = mapped_column(String(2))
    strategy_id: Mapped[str] = mapped_column(String(100))
    strategy_version: Mapped[int] = mapped_column()
    simulation_config: Mapped[dict] = mapped_column(JSON)
    strategy_config: Mapped[dict] = mapped_column(JSON)
    sources: Mapped[list] = mapped_column(JSON)
    metrics: Mapped[dict] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON)
    trade_summary: Mapped[list] = mapped_column(JSON)
    event_summary: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class WalkForwardReport(Base):
    __tablename__ = "walk_forward_reports"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(50))
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id"))
    timeframe: Mapped[str] = mapped_column(String(2))
    strategy_id: Mapped[str] = mapped_column(String(100))
    strategy_version: Mapped[int] = mapped_column()
    simulation_config: Mapped[dict] = mapped_column(JSON)
    strategy_config: Mapped[dict] = mapped_column(JSON)
    sources: Mapped[list] = mapped_column(JSON)
    metrics: Mapped[dict] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON)
    train_size: Mapped[int] = mapped_column()
    test_size: Mapped[int] = mapped_column()
    folds: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class ProviderCredential(Base):
    """Encrypted provider data credential; never projected through an HTTP route."""

    __tablename__ = "provider_credentials"
    __table_args__ = (
        CheckConstraint("provider = 'DHAN'", name="ck_provider_credential_dhan_only"),
    )
    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text)
    key_version: Mapped[int] = mapped_column(default=1)
    client_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rotated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(100))
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    details: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
