"""V2.9C: Add market_candidates table for durable discovery scanner evidence.

Revision ID: 20261109170000_v29c_market_candidates
Revises: 20261109160000_v29_discovery_foundation
"""

from alembic import op
import sqlalchemy as sa

revision = "20261109170000_v29c_market_candidates"
down_revision = "20261109160000_v29_discovery_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "market_candidates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.String(128), nullable=False),
        sa.Column("scanner_id", sa.String(100), nullable=False),
        sa.Column("scanner_version", sa.String(50), nullable=True),
        sa.Column("market", sa.String(50), nullable=False),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("asset_class", sa.String(30), nullable=False),
        sa.Column("instrument_type", sa.String(30), nullable=False),
        sa.Column("underlying", sa.String(100), nullable=False),
        sa.Column("canonical_contract_id", sa.String(255), nullable=True),
        sa.Column("expiry", sa.String(20), nullable=True),
        sa.Column("strike", sa.Numeric(18, 4), nullable=True),
        sa.Column("option_type", sa.String(10), nullable=True),
        sa.Column("discovery_reason", sa.String(255), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_market_candidates_candidate_id", "market_candidates", ["candidate_id"], unique=True)
    op.create_index("ix_market_candidates_scanner", "market_candidates", ["scanner_id"])
    op.create_index("ix_market_candidates_contract", "market_candidates", ["canonical_contract_id"])
    op.create_index("ix_market_candidates_detected", "market_candidates", ["detected_at"])


def downgrade():
    op.drop_index("ix_market_candidates_detected", table_name="market_candidates")
    op.drop_index("ix_market_candidates_contract", table_name="market_candidates")
    op.drop_index("ix_market_candidates_scanner", table_name="market_candidates")
    op.drop_index("ix_market_candidates_candidate_id", table_name="market_candidates")
    op.drop_table("market_candidates")
