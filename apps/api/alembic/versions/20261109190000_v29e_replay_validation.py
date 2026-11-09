"""V2.10D: Add replay validation and calibration foundation.

Revision ID: 20261109190000_v29e_replay_validation
Revises: 20261109180000_v29d_historical_observations
"""

from alembic import op
import sqlalchemy as sa

revision = "20261109190000_v29e_replay_validation"
down_revision = "20261109180000_v29d_historical_observations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "replay_calibration",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("canonical_contract_id", sa.String(255), nullable=False, index=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("calibrated_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("calibration_factor", sa.Numeric(5, 4), nullable=False, server_default="1.0000"),
        sa.Column("missing_engine_adjustment", sa.Numeric(5, 4), nullable=True),
        sa.Column("baseline_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("calibration_type", sa.String(50), nullable=False, default="engine_coverage"),
        sa.Column("engine_coverage_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("observation_count_at_ts", sa.Integer(), nullable=False, default=1),
        sa.Column("calibrated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("validation_status", sa.String(50), nullable=False, default="validated"),
        sa.UniqueConstraint(
            "canonical_contract_id", "observed_at", "calibration_type",
            name="uq_replay_calibration_point_in_time_type"
        ),
    )
    # Add calibration index for score-range queries
    op.create_index(
        "ix_replay_calibration_score",
        "replay_calibration",
        ["calibrated_score"],
    )
    op.create_index(
        "ix_replay_calibration_type",
        "replay_calibration",
        ["calibration_type"],
    )


def downgrade():
    op.drop_index("ix_replay_calibration_score", table_name="replay_calibration")
    op.drop_index("ix_replay_calibration_type", table_name="replay_calibration")
    op.drop_table("replay_calibration")