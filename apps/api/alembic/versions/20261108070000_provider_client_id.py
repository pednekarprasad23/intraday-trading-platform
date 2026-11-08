"""Persist Dhan client ID alongside encrypted access token.

Revision ID: 20261108070000_client_id
Revises: 20261108020326_paper_trading
"""

from alembic import op
import sqlalchemy as sa

revision = "20261108070000_client_id"
down_revision = "20261108020326_paper_trading"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "provider_credentials",
        sa.Column("client_id", sa.String(length=200), nullable=True),
    )


def downgrade():
    op.drop_column("provider_credentials", "client_id")
