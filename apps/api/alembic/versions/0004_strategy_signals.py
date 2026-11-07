"""Immutable strategy configuration versions and accepted signal snapshots.

Revision ID: 0004_strategy_signals
Revises: 0003_historical_candles
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_strategy_signals"
down_revision = "0003_historical_candles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "strategy_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("strategy_id", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("config_sha256", sa.String(64), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "strategy_id", "version", "config_sha256", name="uq_strategy_config"
        ),
    )
    op.create_table(
        "strategy_signals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "strategy_version_id",
            sa.Uuid(),
            sa.ForeignKey("strategy_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id"), nullable=False
        ),
        sa.Column(
            "partition_id",
            sa.Uuid(),
            sa.ForeignKey("historical_partitions.id"),
            nullable=False,
        ),
        sa.Column("decision_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "strategy_version_id",
            "partition_id",
            "input_sha256",
            name="uq_strategy_signal_input",
        ),
    )


def downgrade():
    op.drop_table("strategy_signals")
    op.drop_table("strategy_versions")
