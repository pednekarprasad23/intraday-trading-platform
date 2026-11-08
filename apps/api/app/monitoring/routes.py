"""Monitoring API endpoints for intraday-trading-platform.

Provides health checks, metrics, and operational information.
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_user
from app.config import get_settings

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    dependencies: dict[str, str]
    response_time_ms: float


class MetricsResponse(BaseModel):
    timestamp: str
    uptime_seconds: float
    requests_total: int
    requests_success: int
    requests_error: int
    active_sessions: int
    database_connections: int
    redis_connections: int


class BackupInfo(BaseModel):
    path: str
    size_bytes: int
    created_at: str


class BackupListResponse(BaseModel):
    backups: list[BackupInfo]
    retention_days: int


class StrategyVersion(BaseModel):
    strategy_id: str
    name: Optional[str]
    current_version: Optional[str]
    status: str
    total_snapshots: int


# Global metrics store (in production, use Prometheus/Grafana)
_metrics_store: dict[str, any] = {
    "start_time": time.time(),
    "requests_total": 0,
    "requests_success": 0,
    "requests_error": 0,
}


def get_request_metrics() -> dict:
    """Get current request metrics."""
    return _metrics_store.copy()


def increment_requests(success: bool = True):
    """Increment request counters."""
    _metrics_store["requests_total"] += 1
    if success:
        _metrics_store["requests_success"] += 1
    else:
        _metrics_store["requests_error"] += 1


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Full health check with response time measurement."""
    start_time = time.time()

    dependencies = {}

    # Check database
    try:
        from sqlalchemy import text
        from app.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        dependencies["database"] = "ok"
    except Exception:
        dependencies["database"] = "unavailable"

    # Check Redis
    try:
        import redis
        from app.config import get_settings
        settings = get_settings()
        redis_client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        redis_client.ping()
        dependencies["redis"] = "ok"
    except Exception:
        dependencies["redis"] = "unavailable"

    # Check API container
    try:
        dependencies["api"] = "ok"
    except Exception:
        dependencies["api"] = "unavailable"

    response_time = (time.time() - start_time) * 1000  # Convert to ms

    status = "healthy" if all(v == "ok" for v in dependencies.values()) else "degraded"

    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow().isoformat(),
        dependencies=dependencies,
        response_time_ms=round(response_time, 2),
    )


@router.get("/metrics", response_model=MetricsResponse)
def prometheus_metrics():
    """Prometheus-format metrics endpoint.

    Returns metrics in a format that can be scraped by Prometheus
    or similar monitoring systems.
    """
    start_time = time.time()
    metrics = get_request_metrics()

    uptime = time.time() - metrics["start_time"]

    # Count active sessions from Redis
    active_sessions = 0
    try:
        import redis
        from app.config import get_settings
        settings = get_settings()
        redis_client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        # Count session keys
        active_sessions = len(redis_client.keys("session:*"))
    except Exception:
        pass

    # Database connections (approximation)
    db_connections = 0
    try:
        from sqlalchemy import text
        from app.database import engine
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE datname = 'intraday_trading'")
            )
            row = result.fetchone()
            db_connections = row[0] if row else 0
    except Exception:
        pass

    return MetricsResponse(
        timestamp=datetime.utcnow().isoformat(),
        uptime_seconds=round(uptime, 2),
        requests_total=metrics["requests_total"],
        requests_success=metrics["requests_success"],
        requests_error=metrics["requests_error"],
        active_sessions=active_sessions,
        database_connections=db_connections,
        redis_connections=active_sessions,  # Approximate
    )


@router.get("/backups", response_model=BackupListResponse, dependencies=[Depends(require_user)])
def list_backups(
    backup_dir: Optional[str] = None,
    retention_days: int = 7,
):
    """List recent backups available for restore.

    Requires authentication.
    """
    if backup_dir is None:
        backup_dir = os.environ.get("BACKUP_DIR", "deployment/backups")

    backup_path = Path(backup_dir)

    if not backup_path.exists():
        return BackupListResponse(backups=[], retention_days=retention_days)

    # Find all backup files
    backups = []

    # PostgreSQL backups
    pg_backups = sorted(
        backup_path.glob("backup_*.pgdump.gz"),
        key=lambda p: p.stat().st_ctime,
        reverse=True,
    )

    for backup_file in pg_backups:
        stat = backup_file.stat()
        backups.append(BackupInfo(
            path=str(backup_file.name),
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
        ))

    # Also check custom format backups
    custom_backups = sorted(
        backup_path.glob("backup_*.tar.gz"),
        key=lambda p: p.stat().st_ctime,
        reverse=True,
    )

    for backup_file in custom_backups:
        stat = backup_file.stat()
        name = backup_file.stem  # Remove .gz
        if not name.startswith("backup_"):
            name = backup_file.name
        backups.append(BackupInfo(
            path=str(backup_file.name),
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
        ))

    return BackupListResponse(
        backups=backups[:retention_days],
        retention_days=retention_days,
    )


@router.get("/strategy/versions", response_model=list[StrategyVersion])
def list_strategy_versions(
    strategy_id: Optional[str] = None,
):
    """List all strategies and their versions.

    Args:
        strategy_id: Optional filter to get a specific strategy
    """
    from app.monitoring.performance import (
        STRATEGY_REGISTRY,
        get_strategy_versions as get_versions,
    )

    if strategy_id:
        result = get_versions(strategy_id)
        return [
            StrategyVersion(
                strategy_id=result.get("strategy_id", strategy_id),
                name=result.get("name"),
                current_version=result.get("current_version"),
                status=result.get("status", "draft"),
                total_snapshots=result.get("total_snapshots", 0),
            )
        ]

    versions = []
    for sid, data in STRATEGY_REGISTRY.items():
        versions.append(StrategyVersion(
            strategy_id=sid,
            name=data.get("name"),
            current_version=data.get("current_version"),
            status=data.get("status", "draft"),
            total_snapshots=sum(
                len(v.get("metrics", []))
                for v in data.get("versions", {}).values()
            ),
        ))

    return versions


# Prometheus exposition format
@router.get("/metrics/prometheus")
def metrics_prometheus():
    """Prometheus text format metrics."""
    lines = []
    lines.append("# HELP intraday_requests_total Total number of requests")
    lines.append("# TYPE intraday_requests_total counter")

    metrics = get_request_metrics()
    lines.append(f"intraday_requests_total {metrics['requests_total']}")
    lines.append(f"intraday_requests_success {metrics['requests_success']}")
    lines.append(f"intraday_requests_error {metrics['requests_error']}")

    uptime = time.time() - metrics["start_time"]
    lines.append(f"# HELP intraday_uptime_seconds Application uptime")
    lines.append("# TYPE intraday_uptime_seconds gauge")
    lines.append(f"intraday_uptime_seconds {uptime}")

    return "\n".join(lines) + "\n"