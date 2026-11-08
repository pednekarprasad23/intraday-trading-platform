"""Add instrument metadata to historical partitions.

Revision ID: 20261108090000
Revises: 20261108070000_client_id
"""

from alembic import op
import sqlalchemy as sa

revision = "20261108090000"
down_revision = "20261108070000_client_id"
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns for instrument metadata
    op.add_column(
        "historical_partitions",
        sa.Column("instrument_canonical_symbol", sa.String(100), nullable=True),
    )
    op.add_column(
        "historical_partitions",
        sa.Column("instrument_display_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "historical_partitions",
        sa.Column("underlying_canonical_symbol", sa.String(100), nullable=True),
    )
    op.add_column(
        "historical_partitions",
        sa.Column("option_type", sa.String(2), nullable=True),
    )
    op.add_column(
        "historical_partitions",
        sa.Column("strike_price", sa.Numeric(precision=18, scale=4), nullable=True),
    )


def downgrade():
    op.drop_column("historical_partitions", "strike_price")
    op.drop_column("historical_partitions", "option_type")
    op.drop_column("historical_partitions", "underlying_canonical_symbol")
    op.drop_column("historical_partitions", "instrument_display_name")
    op.drop_column("historical_partitions", "instrument_canonical_symbol")
