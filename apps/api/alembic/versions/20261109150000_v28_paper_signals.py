"""V2.8B: Add paper_signals table and paper_orders traceability (project_id, strategy_version_id, signal_id).

Revision ID: 20261109150000_v28_paper_signals
Revises: 20261109140000_v26_runtime
"""

from alembic import op
import sqlalchemy as sa

revision = "20261109150000_v28_paper_signals"
down_revision = "20261109140000_v26_runtime"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "paper_signals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), sa.ForeignKey("strategy_versions.id"), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("signal_type", sa.String(20), nullable=False),
        sa.Column("requested_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("reference_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("stop_loss", sa.Numeric(18, 4), nullable=True),
        sa.Column("take_profit", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(30), server_default="RECEIVED", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_paper_signals_correlation_id", "paper_signals", ["correlation_id"], unique=True)
    op.create_index("ix_paper_signals_project_id", "paper_signals", ["project_id"])

    # Add traceability columns to paper_orders
    with op.batch_alter_table("paper_orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="SET NULL", name="fk_paper_orders_project_id"), nullable=True))
        batch_op.add_column(sa.Column("strategy_version_id", sa.Uuid(), sa.ForeignKey("strategy_versions.id", name="fk_paper_orders_strategy_version_id"), nullable=True))
        batch_op.add_column(sa.Column("signal_id", sa.Uuid(), sa.ForeignKey("paper_signals.id", ondelete="SET NULL", name="fk_paper_orders_signal_id"), nullable=True))
        batch_op.create_unique_constraint("uq_paper_orders_signal_id", ["signal_id"])


def downgrade():
    with op.batch_alter_table("paper_orders", schema=None) as batch_op:
        batch_op.drop_constraint("uq_paper_orders_signal_id", type_="unique")
        batch_op.drop_constraint("fk_paper_orders_signal_id", type_="foreignkey")
        batch_op.drop_constraint("fk_paper_orders_strategy_version_id", type_="foreignkey")
        batch_op.drop_constraint("fk_paper_orders_project_id", type_="foreignkey")
        batch_op.drop_column("signal_id")
        batch_op.drop_column("strategy_version_id")
        batch_op.drop_column("project_id")
    op.drop_index("ix_paper_signals_project_id", table_name="paper_signals")
    op.drop_index("ix_paper_signals_correlation_id", table_name="paper_signals")
    op.drop_table("paper_signals")
