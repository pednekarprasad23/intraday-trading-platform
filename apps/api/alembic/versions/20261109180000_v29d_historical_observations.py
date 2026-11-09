"""V2.10A: Add historical_observations table for durable point-in-time market observations.

Revision ID: 20261109180000_v29d_historical_observations
Revises: 20261109170000_v29c_market_candidates
"""

from alembic import op
import sqlalchemy as sa

revision = "20261109180000_v29d_historical_observations"
down_revision = "20261109170000_v29c_market_candidates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "historical_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("canonical_contract_id", sa.String(255), nullable=False, index=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("market", sa.String(50), nullable=False),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("underlying", sa.String(100), nullable=False),
        sa.Column("instrument_type", sa.String(50), nullable=False),
        sa.Column("expiry", sa.String(50), nullable=True),
        sa.Column("strike", sa.Numeric(18, 4), nullable=True),
        sa.Column("option_type", sa.String(20), nullable=True),
        sa.Column("spot_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("last_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("open_interest", sa.Integer(), nullable=True),
        sa.Column("bid_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("ask_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("implied_volatility", sa.Numeric(10, 4), nullable=True),
        sa.Column("delta", sa.Numeric(10, 6), nullable=True),
        sa.Column("gamma", sa.Numeric(10, 6), nullable=True),
        sa.Column("theta", sa.Numeric(10, 6), nullable=True),
        sa.Column("vega", sa.Numeric(10, 6), nullable=True),
        sa.Column("lot_size", sa.Integer(), nullable=True),
        sa.Column("tick_size", sa.Numeric(10, 4), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default="fixture"),
        sa.Column("provider_instrument_id", sa.String(100), nullable=True),
        sa.Column("scanner_version", sa.String(50), nullable=True),
        sa.Column("analysis_engine_versions", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("canonical_contract_id", "observed_at", name="uq_historical_observation_point_in_time"),
    )


def downgrade():
    op.drop_table("historical_observations")