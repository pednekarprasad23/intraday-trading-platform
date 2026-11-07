"""Add provider metadata and explicit demo provenance.

Revision ID: 0002_market_metadata
Revises: 0001_foundation
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_market_metadata"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "instruments",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "provider_symbols", sa.Column("provider_exchange", sa.String(50), nullable=True)
    )
    op.add_column(
        "provider_symbols",
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "provider_symbols",
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "provider_symbols",
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("provider_symbols", "last_verified_at")
    op.drop_column("provider_symbols", "valid_to")
    op.drop_column("provider_symbols", "valid_from")
    op.drop_column("provider_symbols", "provider_exchange")
    op.drop_column("instruments", "is_demo")
