"""V2.9A: Add market_universes table for universal market discovery foundation.

Revision ID: 20261109160000_v29_discovery_foundation
Revises: 20261109150000_v28_paper_signals
"""

from alembic import op
import sqlalchemy as sa

revision = "20261109160000_v29_discovery_foundation"
down_revision = "20261109150000_v28_paper_signals"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "market_universes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("market", sa.String(50), server_default="INDIA", nullable=False),
        sa.Column("exchange", sa.String(50), server_default="NSE", nullable=False),
        sa.Column("asset_class", sa.String(30), nullable=False),
        sa.Column("instrument_type", sa.String(30), nullable=False),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("underlying", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(50), server_default="DEMO", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("universe_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_market_universes_name", "market_universes", ["name"], unique=True)


def downgrade():
    op.drop_index("ix_market_universes_name", table_name="market_universes")
    op.drop_table("market_universes")
