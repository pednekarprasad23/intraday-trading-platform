"""Paper trading models: accounts, orders, fills, positions, risk events, kill switch.

Revision ID: 20261108020326_paper_trading
Revises: 0006_provider_credentials
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20261108020326_paper_trading"
down_revision = "0006_provider_credentials"
branch_labels = None
depends_on = None


def upgrade():
    # paper_accounts table
    op.create_table(
        "paper_accounts",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("initial_capital", sa.Numeric(18, 2), nullable=False),
        sa.Column("available_capital", sa.Numeric(18, 2), nullable=False),
        sa.Column("max_position_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("max_daily_loss", sa.Numeric(18, 2), nullable=False),
        sa.Column("max_total_exposure", sa.Numeric(18, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("currency IN ('INR', 'USD')", name="ck_paper_currency"),
    )

    # paper_orders table
    op.create_table(
        "paper_orders",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("account_id", UUID(), sa.ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instrument_id", UUID(), sa.ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("order_type", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("price", sa.Numeric(18, 4), nullable=True),
        sa.Column("stop_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("time_in_force", sa.String(20), nullable=False, server_default="DAY"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_order_id", UUID(), sa.ForeignKey("paper_orders.id"), nullable=True),
        sa.Column("strategy_id", sa.String(100), nullable=True),
        sa.Column("strategy_version", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_paper_side"),
        sa.CheckConstraint(
            "order_type IN ('market', 'limit', 'stop', 'stop_limit')",
            name="ck_paper_order_type",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'submitted', 'filled', 'partial', 'rejected', 'cancelled', 'expired', 'uncertain')",
            name="ck_paper_state",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_paper_idempotency"),
        sa.Index("ix_paper_account_state", "account_id", "state"),
        sa.Index("ix_paper_instrument_state", "instrument_id", "state"),
    )

    # paper_fills table
    op.create_table(
        "paper_fills",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("order_id", UUID(), sa.ForeignKey("paper_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fill_sequence", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("commission", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("fees", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("slippage", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provenance", sa.String(50), nullable=False, server_default="PAPER_SIM"),
        sa.UniqueConstraint("order_id", "fill_sequence", name="uq_paper_fill_seq"),
        sa.Index("ix_paper_fill_time", "filled_at"),
    )

    # paper_positions table
    op.create_table(
        "paper_positions",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("account_id", UUID(), sa.ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instrument_id", UUID(), sa.ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_entry_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("unrealized_pnl", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("realized_pnl", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("last_marked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "instrument_id", name="uq_paper_position"),
        sa.Index("ix_paper_position_account", "account_id"),
    )

    # paper_risk_events table
    op.create_table(
        "paper_risk_events",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("account_id", UUID(), sa.ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("order_id", UUID(), sa.ForeignKey("paper_orders.id"), nullable=True),
        sa.Column("instrument_id", UUID(), sa.ForeignKey("instruments.id"), nullable=True),
        sa.Column("details", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('daily_loss_limit', 'position_limit', 'exposure_limit', 'instrument_blocked', 'kill_switch', 'stale_data', 'insufficient_capital', 'max_orders_per_session')",
            name="ck_paper_risk_type",
        ),
        sa.Index("ix_paper_risk_account_time", "account_id", "created_at"),
    )

    # kill_switch table
    op.create_table(
        "kill_switch",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, server_default="global"),
        sa.Column("state", sa.String(20), nullable=False, server_default="armed"),
        sa.Column("triggered_by", UUID(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reset_by", UUID(), nullable=True),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_triggered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_kill_switch"),
    )


def downgrade():
    op.drop_table("kill_switch")
    op.drop_table("paper_risk_events")
    op.drop_table("paper_positions")
    op.drop_table("paper_fills")
    op.drop_table("paper_orders")
    op.drop_table("paper_accounts")