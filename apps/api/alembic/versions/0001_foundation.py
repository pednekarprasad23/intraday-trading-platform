"""Foundation tables.

Revision ID: 0001_foundation
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "instruments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("canonical_symbol", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("asset_class", sa.String(30), nullable=False),
        sa.Column("exchange", sa.String(30), nullable=False),
        sa.Column("segment", sa.String(50), nullable=False),
        sa.Column("underlying_id", sa.Uuid(), sa.ForeignKey("instruments.id")),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("strike_price", sa.Numeric(18, 4)),
        sa.Column("option_type", sa.String(2)),
        sa.Column("lot_size", sa.Numeric(18, 4)),
        sa.Column("tick_size", sa.Numeric(18, 4)),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("data_available", sa.Boolean(), nullable=False),
        sa.Column("execution_enabled", sa.Boolean(), nullable=False),
        sa.Column("metadata_source", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_instruments_canonical_symbol",
        "instruments",
        ["canonical_symbol"],
        unique=True,
    )
    op.create_table(
        "provider_symbols",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id"), nullable=False
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_instrument_key", sa.String(200), nullable=False),
        sa.Column("data_enabled", sa.Boolean(), nullable=False),
        sa.Column("execution_enabled", sa.Boolean(), nullable=False),
        sa.UniqueConstraint(
            "provider", "provider_instrument_key", name="uq_provider_symbol"
        ),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("audit_logs")
    op.drop_table("provider_symbols")
    op.drop_index("ix_instruments_canonical_symbol", "instruments")
    op.drop_table("instruments")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
