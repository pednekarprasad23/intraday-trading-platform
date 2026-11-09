"""Project control-plane database models (V2.6 Phase 3)."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, utcnow, StrategyVersion


class ProjectStatus(str, Enum):
    CREATED = "CREATED"
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    ERROR = "ERROR"
    ARCHIVED = "ARCHIVED"


class ExecutionMode(str, Enum):
    PAPER = "PAPER"
    LIVE_DISABLED = "LIVE_DISABLED"


class RunStatus(str, Enum):
    QUEUED = "QUEUED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(ProjectStatus), default=ProjectStatus.CREATED, nullable=False
    )
    execution_mode: Mapped[ExecutionMode] = mapped_column(
        SQLEnum(ExecutionMode), default=ExecutionMode.PAPER, nullable=False
    )
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    config_version: Mapped[int] = mapped_column(default=1, nullable=False)

    # V2.6 Phase 3 Runtime Tracking Fields
    runtime_status: Mapped[str] = mapped_column(String(50), default="STOPPED", nullable=False)
    runtime_instance_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    strategies: Mapped[list["ProjectStrategyAssignment"]] = relationship(
        "ProjectStrategyAssignment", back_populates="project", cascade="all, delete-orphan"
    )
    runs: Mapped[list["ProjectRun"]] = relationship(
        "ProjectRun", back_populates="project", cascade="all, delete-orphan"
    )


class ProjectStrategyAssignment(Base):
    __tablename__ = "project_strategy_assignments"
    __table_args__ = (
        UniqueConstraint("project_id", "strategy_id", name="uq_project_strategy"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="primary", nullable=False)
    priority: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="strategies")


class ProjectRun(Base):
    __tablename__ = "project_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    strategy_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("strategy_versions.id"), nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        SQLEnum(RunStatus), default=RunStatus.QUEUED, nullable=False
    )
    parameters_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    parameters_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by: Mapped[UUID | None] = mapped_column(nullable=True)
    runtime_instance_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="runs")
