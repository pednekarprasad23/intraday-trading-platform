"""V2.6 Phase 3: Project runtime foundation and sandboxed execution runs (project_runs, project runtime tracking).

Revision ID: 2061109140000_v26_runtime (or 20261109140000_v26_runtime)
Revises: 20261109130000_v26_projects
"""

from alembic import op
import sqlalchemy as sa

revision = "20261109140000_v26_runtime"
down_revision = "20261109130000_v26_projects"
branch_labels = None
depends_on = None


def upgrade():
    # Add runtime tracking columns to projects table
    op.add_column("projects", sa.Column("runtime_status", sa.String(50), server_default="STOPPED", nullable=False))
    op.add_column("projects", sa.Column("runtime_instance_id", sa.String(100), nullable=True))
    op.add_column("projects", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("last_error", sa.Text(), nullable=True))

    # Create project_runs table
    op.create_table(
        "project_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), sa.ForeignKey("strategy_versions.id"), nullable=False),
        sa.Column("status", sa.String(50), server_default="QUEUED", nullable=False),
        sa.Column("parameters_snapshot", sa.JSON(), nullable=False),
        sa.Column("parameters_sha256", sa.String(64), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("runtime_instance_id", sa.String(100), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("project_runs")
    op.drop_column("projects", "last_error")
    op.drop_column("projects", "heartbeat_at")
    op.drop_column("projects", "runtime_instance_id")
    op.drop_column("projects", "runtime_status")
