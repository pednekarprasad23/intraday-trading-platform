"""Encrypted read-only provider credentials.

Revision ID: 0006_provider_credentials
Revises: 0005_research_reports
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_provider_credentials"
down_revision = "0005_research_reports"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "provider_credentials",
        sa.Column("provider", sa.String(50), primary_key=True),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider = 'DHAN'", name="ck_provider_credential_dhan_only"
        ),
    )


def downgrade():
    op.drop_table("provider_credentials")
