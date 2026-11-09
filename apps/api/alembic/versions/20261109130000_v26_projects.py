"""V2.6 Phase 2: Project control-plane foundation (projects, project_strategy_assignments).

Revision ID: 20261109130000_v26_projects
Revises: 20261109120000_v26_research_integration
"""

from alembic import op
import sqlalchemy as sa

revision = "20261109130000_v26_projects"
down_revision = "20261109120000_v26_research_integration"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="CREATED"),
        sa.Column("execution_mode", sa.String(50), nullable=False, server_default="PAPER"),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_name", "projects", ["name"], unique=True)
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=True)

    op.create_table(
        "project_strategy_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("strategy_id", sa.String(100), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="primary"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "strategy_id", name="uq_project_strategy"),
    )


def downgrade():
    op.drop_table("project_strategy_assignments")
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_table("projects")
