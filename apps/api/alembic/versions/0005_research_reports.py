"""Persisted bounded research report projections.

Revision ID: 0005_research_reports
Revises: 0004_strategy_signals
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_research_reports"
down_revision = "0004_strategy_signals"
branch_labels = None
depends_on = None


def _common_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column(
            "instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id"), nullable=False
        ),
        sa.Column("timeframe", sa.String(2), nullable=False),
        sa.Column("strategy_id", sa.String(100), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("simulation_config", sa.JSON(), nullable=False),
        sa.Column("strategy_config", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.add_column(
        "historical_import_jobs",
        sa.Column("provider_response_sha256", sa.String(64), nullable=True),
    )
    op.add_column(
        "historical_import_jobs",
        sa.Column("provider_retrieved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "research_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id"), nullable=False
        ),
        sa.Column(
            "partition_id",
            sa.Uuid(),
            sa.ForeignKey("historical_partitions.id"),
            nullable=False,
        ),
        sa.Column("strategy_id", sa.String(100), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("strategy_config_sha256", sa.String(64), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("decision_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("quality", sa.String(20), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "partition_id",
            "strategy_config_sha256",
            "input_sha256",
            name="uq_research_evaluation_input",
        ),
    )
    op.create_table(
        "backtest_reports",
        *_common_columns(),
        sa.Column("trade_summary", sa.JSON(), nullable=False),
        sa.Column("event_summary", sa.JSON(), nullable=False),
    )
    op.create_table(
        "walk_forward_reports",
        *_common_columns(),
        sa.Column("train_size", sa.Integer(), nullable=False),
        sa.Column("test_size", sa.Integer(), nullable=False),
        sa.Column("folds", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("walk_forward_reports")
    op.drop_table("backtest_reports")
    op.drop_table("research_evaluations")
    op.drop_column("historical_import_jobs", "provider_retrieved_at")
    op.drop_column("historical_import_jobs", "provider_response_sha256")
