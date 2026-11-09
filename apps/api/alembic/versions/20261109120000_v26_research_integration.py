"""V2.6 Phase 1: Research and backtesting integration schema additions (strategy_version_id, config_snapshot, config_sha256).

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
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "strategy_version_id",
                    sa.Uuid(),
                    sa.ForeignKey("strategy_versions.id", name=f"fk_{table}_strategy_version_id"),
                    nullable=True,
                )
            )
            batch_op.add_column(
                sa.Column("config_snapshot", sa.JSON(), nullable=True)
            )
            batch_op.add_column(
                sa.Column("config_sha256", sa.String(64), nullable=True)
            )


def downgrade():
    for table in ("walk_forward_reports", "backtest_reports"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_strategy_version_id", type_="foreignkey")
            batch_op.drop_column("config_sha256")
            batch_op.drop_column("config_snapshot")
            batch_op.drop_column("strategy_version_id")
