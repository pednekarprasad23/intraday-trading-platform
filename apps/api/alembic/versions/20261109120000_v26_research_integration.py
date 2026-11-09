"""V2.6 Phase 1: Research and backtesting integration schema additions.

Revision ID: 20261109120000_v26_research_integration
Revises: 20261108090000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261109120000_v26_research_integration"
down_revision = "20261108090000"
branch_labels = None
depends_on = None


def upgrade():
    # Add strategy version association and config snapshots to research reports (backtest_reports, walk_forward_reports)
    for table in ("backtest_reports", "walk_forward_reports"):
        op.add_column(
            table,
            sa.Column(
                "strategy_version_id",
                sa.Uuid(),
                sa.ForeignKey("strategy_versions.id"),
                nullable=True,
            ),
        )
        op.add_column(
            table,
            sa.Column("project_id", sa.Uuid(), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("config_snapshot", sa.JSON(), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("config_sha256", sa.String(64), nullable=True),
        )

    # Add project_id to strategy_signals (schema-ready for future Project backfill)
    op.add_column(
        "strategy_signals",
        sa.Column("project_id", sa.Uuid(), nullable=True),
    )


def downgrade():
    op.drop_column("strategy_signals", "project_id")
    for table in ("walk_forward_reports", "backtest_reports"):
        op.drop_column(table, "config_sha256")
        op.drop_column(table, "config_snapshot")
        op.drop_column(table, "project_id")
        op.drop_column(table, "strategy_version_id")
