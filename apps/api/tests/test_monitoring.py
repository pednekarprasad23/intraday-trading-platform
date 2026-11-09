"""Tests for monitoring module.

Tests for health checks, metrics, backup listing, and strategy versions.
"""

import os
import sys
from datetime import date
from decimal import Decimal as D
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from app.monitoring.performance import (
    record_performance,
    get_strategy_history,
    get_lifecycle,
    detect_drift,
    get_strategy_versions,
    STRATEGY_REGISTRY,
    register_strategy,
    StrategyStatus,
)
from app.backtesting.reports import BacktestReport


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_header():
    """Get authentication header for tests.

    Note: In a real test, you would need to create a user and get a session cookie.
    For now, we test endpoints that don't require auth or mock the auth.
    """
    # This will need actual auth tokens in integration tests
    return {}


class TestHealthEndpoint:
    """Tests for /api/v1/monitoring/health endpoint."""

    def test_health_check_returns_200(self, client):
        """Health check should return 200 OK with status info."""
        response = client.get("/api/v1/monitoring/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "dependencies" in data
        assert "response_time_ms" in data

        # Should have database and redis in dependencies
        assert "database" in data["dependencies"]
        assert "redis" in data["dependencies"]

    def test_health_response_format(self, client):
        """Health response should have correct types."""
        response = client.get("/api/v1/monitoring/health")
        data = response.json()

        assert isinstance(data["status"], str)
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["dependencies"], dict)
        assert isinstance(data["response_time_ms"], (int, float))


class TestMetricsEndpoint:
    """Tests for /api/v1/monitoring/metrics endpoint."""

    def test_metrics_returns_200(self, client):
        """Metrics endpoint should return 200 OK."""
        response = client.get("/api/v1/monitoring/metrics")

        assert response.status_code == 200
        data = response.json()

        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert "requests_total" in data

    def test_metrics_prometheus_format(self, client):
        """Metrics should also be available in Prometheus format."""
        response = client.get("/api/v1/monitoring/metrics/prometheus")

        assert response.status_code == 200
        content = response.text

        # Should have Prometheus-style metrics
        assert "intraday_requests_total" in content
        assert "intraday_uptime_seconds" in content


class TestBackupsEndpoint:
    """Tests for /api/v1/monitoring/backups endpoint."""

    @pytest.mark.skipif(
        os.getenv("AUTH_DISABLED", "false").lower() == "true",
        reason="Development mode: AUTH_DISABLED=true, production auth behavior tested separately",
    )
    def test_backups_requires_auth(self, client, monkeypatch):
        """Backups endpoint should require authentication."""
        from app.config import get_settings
        orig_settings = get_settings()
        class ProdSettings:
            app_env = "production"
            auth_disabled = False
            redis_url = orig_settings.redis_url
            database_url = orig_settings.database_url
            session_ttl_seconds = orig_settings.session_ttl_seconds
            mt5_snapshot_path = orig_settings.mt5_snapshot_path
            angelone_snapshot_path = orig_settings.angelone_snapshot_path
            angelone_enabled = orig_settings.angelone_enabled
            historical_data_root = orig_settings.historical_data_root
            credential_key_path = orig_settings.credential_key_path
            app_name = orig_settings.app_name
            app_version = orig_settings.app_version
        monkeypatch.setattr("app.auth.get_settings", lambda: ProdSettings())
        monkeypatch.setattr("app.main.get_settings", lambda: ProdSettings())
        monkeypatch.setattr("app.monitoring.routes.get_settings", lambda: ProdSettings())

        response = client.get("/api/v1/monitoring/backups")

        assert response.status_code == 401  # Unauthorized

    def test_backups_returns_list_format(self, client):
        """Backups list should have correct structure with auth."""
        # Mock require_user dependency
        with patch("app.auth.require_user") as mock_auth:
            mock_auth.return_value = {"user_id": "test"}

            response = client.get("/api/v1/monitoring/backups")

            assert response.status_code == 200
            data = response.json()

            assert "backups" in data
            assert "retention_days" in data
            assert isinstance(data["backups"], list)

    def test_backups_list_empty_when_no_backups(self, client):
        """Should return empty list when no backups exist."""
        with patch("app.auth.require_user") as mock_auth:
            mock_auth.return_value = {"user_id": "test"}

            with patch.dict(os.environ, {"BACKUP_DIR": "/nonexistent/backups"}):
                response = client.get("/api/v1/monitoring/backups")

                assert response.status_code == 200
                data = response.json()
                assert data["backups"] == []


class TestStrategyVersionsEndpoint:
    """Tests for /api/v1/monitoring/strategy/versions endpoint."""

    def test_strategy_versions_returns_list(self, client):
        """Strategy versions should return a list."""
        response = client.get("/api/v1/monitoring/strategy/versions")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)


class TestPerformanceFunctions:
    """Tests for performance tracking functions."""

    def setup_method(self):
        """Clear registry before each test."""
        STRATEGY_REGISTRY.clear()

    def test_register_strategy(self):
        """Strategy registration should work correctly."""
        result = register_strategy(
            strategy_id="test_strategy",
            name="Test Strategy",
            version="1.0.0",
            description="Test description",
        )

        assert result["strategy_id"] == "test_strategy"
        assert result["name"] == "Test Strategy"
        assert result["current_version"] == "1.0.0"
        assert "1.0.0" in result["versions"]

    def test_record_performance(self):
        """Recording performance should store metrics."""
        register_strategy("test_strat", "Test Strategy", "1.0.0")

        # Create a mock report
        report = MagicMock(spec=BacktestReport)
        report.metrics = {
            "total_return": D("0.15"),
            "sharpe_ratio": 1.5,
            "win_rate": 0.6,
        }
        report.strategy_version = "1.0.0"
        report.fingerprint = "abc123"

        snapshot = record_performance("test_strat", report, date(2026, 11, 8))

        assert snapshot["strategy_id"] == "test_strat"
        assert snapshot["version"] == "1.0.0"
        assert snapshot["metrics"]["total_return"] == D("0.15")

    def test_get_strategy_history(self):
        """Getting strategy history should return stored snapshots."""
        register_strategy("test_strat", "Test Strategy", "1.0.0")

        report = MagicMock(spec=BacktestReport)
        report.metrics = {"total_return": D("0.15"), "sharpe_ratio": 1.5}
        report.strategy_version = "1.0.0"
        report.fingerprint = "abc123"

        record_performance("test_strat", report, date(2026, 11, 8))

        history = get_strategy_history("test_strat")

        assert len(history) == 1
        assert history[0]["strategy_id"] == "test_strat"

    def test_get_lifecycle(self):
        """Getting lifecycle should return strategy info."""
        register_strategy("test_strat", "Test Strategy", "1.0.1")

        lifecycle = get_lifecycle("test_strat")

        assert lifecycle["strategy_id"] == "test_strat"
        assert lifecycle["name"] == "Test Strategy"
        assert lifecycle["current_version"] == "1.0.1"

    def test_detect_drift_no_history(self):
        """Drift detection with no history should return appropriate status."""
        result = detect_drift("nonexistent_strategy")

        assert result["drift_detected"] == False
        assert result["reason"] == "insufficient_history"

    def test_detect_drift_with_history(self):
        """Drift detection should compare recent vs historical."""
        register_strategy("test_strat", "Test Strategy", "1.0.0")

        # Add historical metrics
        report1 = MagicMock(spec=BacktestReport)
        report1.metrics = {"total_return": D("0.10"), "sharpe_ratio": 1.0}
        report1.strategy_version = "1.0.0"
        report1.fingerprint = "abc123"

        record_performance("test_strat", report1, date(2026, 11, 1))

        # Add recent metrics with significant drift
        from app.monitoring.performance import STRATEGY_REGISTRY
        recent_metrics = {
            "total_return": D("0.50"),  # 5x previous
            "sharpe_ratio": 1.0,
        }

        STRATEGY_REGISTRY["test_strat"]["versions"]["1.0.0"]["metrics"].append({
            "strategy_id": "test_strat",
            "version": "1.0.0",
            "session_date": "2026-11-08",
            "timestamp": "2026-11-08T00:00:00",
            "metrics": recent_metrics,
            "fingerprint": "def456",
        })

        result = detect_drift("test_strat", threshold=D("0.1"))

        assert result["drift_detected"] == True
        assert len(result["drifts"]) > 0
        assert "total_return" in result["drifts"]

    def test_get_strategy_versions(self):
        """Getting strategy versions should return version info."""
        register_strategy("test_strat", "Test Strategy", "1.0.0")

        versions = get_strategy_versions("test_strat")

        assert versions["strategy_id"] == "test_strat"
        assert versions["name"] == "Test Strategy"
        assert versions["current_version"] == "1.0.0"


class TestPrometheusMetrics:
    """Tests for Prometheus format metrics."""

    def test_prometheus_metrics_format(self, client):
        """Prometheus metrics should be in text format."""
        response = client.get("/api/v1/monitoring/metrics/prometheus")

        content = response.text

        # Format check: should have HELP and TYPE lines
        assert "HELP intraday_" in content
        assert "TYPE intraday_" in content

        # Should have metric values
        assert "intraday_requests_total" in content


# Integration-style tests that need auth
@pytest.mark.integration
class TestMonitoringWithAuth:
    """Integration tests requiring authentication."""

    @pytest.mark.skipif(
        os.getenv("AUTH_DISABLED", "false").lower() == "true",
        reason="Development mode: AUTH_DISABLED=true, production auth behavior tested separately",
    )
    def test_backups_endpoint_with_valid_session(self, client):
        """Backups endpoint should work with valid session cookie."""
        # This test would need to:
        # 1. Create a test user
        # 2. Login to get session cookie
        # 3. Call the backups endpoint

        # For now, skip if auth not configured
        pytest.skip("Requires auth setup")

    @pytest.mark.skipif(
        os.getenv("AUTH_DISABLED", "false").lower() == "true",
        reason="Development mode: AUTH_DISABLED=true, production auth behavior tested separately",
    )
    def test_backups_endpoint_with_invalid_session(self, client, monkeypatch):
        """Backups endpoint should reject invalid session."""
        from app.config import get_settings
        orig_settings = get_settings()
        class ProdSettings:
            app_env = "production"
            auth_disabled = False
            redis_url = orig_settings.redis_url
            database_url = orig_settings.database_url
            session_ttl_seconds = orig_settings.session_ttl_seconds
            mt5_snapshot_path = orig_settings.mt5_snapshot_path
            angelone_snapshot_path = orig_settings.angelone_snapshot_path
            angelone_enabled = orig_settings.angelone_enabled
            historical_data_root = orig_settings.historical_data_root
            credential_key_path = orig_settings.credential_key_path
            app_name = orig_settings.app_name
            app_version = orig_settings.app_version
        monkeypatch.setattr("app.auth.get_settings", lambda: ProdSettings())
        monkeypatch.setattr("app.main.get_settings", lambda: ProdSettings())
        monkeypatch.setattr("app.monitoring.routes.get_settings", lambda: ProdSettings())

        response = client.get(
            "/api/v1/monitoring/backups",
            cookies={"session": "invalid_token"}
        )

        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])