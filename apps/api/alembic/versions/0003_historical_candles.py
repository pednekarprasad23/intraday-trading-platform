"""Catalog immutable offline historical option-candle imports.

Revision ID: 0003_historical_candles
Revises: 0002_market_metadata
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_historical_candles"
down_revision = "0002_market_metadata"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "historical_import_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_instrument_key", sa.String(200), nullable=False),
        sa.Column(
            "instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id"), nullable=False
        ),
        sa.Column("timeframe", sa.String(2), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("requested_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_from", sa.DateTime(timezone=True)),
        sa.Column("observed_to", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("reject_count", sa.Integer(), nullable=False),
        sa.Column("gap_count", sa.Integer(), nullable=False),
        sa.Column("conflict_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "provider",
            "instrument_id",
            "timeframe",
            "source_sha256",
            "session_date",
            name="uq_historical_source",
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')", name="ck_historical_status"
        ),
    )
    op.create_table(
        "historical_partitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("historical_import_jobs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column(
            "instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id"), nullable=False
        ),
        sa.Column("timeframe", sa.String(2), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("relative_path", sa.String(500), nullable=False, unique=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "provider",
            "instrument_id",
            "timeframe",
            "session_date",
            name="uq_historical_partition",
        ),
    )
    op.create_table(
        "historical_gaps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("historical_import_jobs.id"),
            nullable=False,
        ),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "bar_time", name="uq_historical_gap"),
    )


def downgrade():
    op.drop_table("historical_gaps")
    op.drop_table("historical_partitions")
    op.drop_table("historical_import_jobs")
