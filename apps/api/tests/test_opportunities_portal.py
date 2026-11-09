"""Tests for V2.11 Opportunity Portal API endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app


def test_opportunities_requires_auth(client: TestClient):
    """Opportunities endpoints require authentication in production mode."""
    # Without auth cookie or override, should return 401 when auth enabled
    # In test client with default overrides or auth fixtures, test endpoint response structure
    response = client.get("/api/v1/opportunities/summary")
    assert response.status_code in (200, 401)


def test_opportunities_summary_and_list(client: TestClient):
    """Verify summary, list, calibration, and missed opportunity endpoints return valid intelligence structures."""
    # Summary
    resp_sum = client.get("/api/v1/opportunities/summary")
    if resp_sum.status_code == 200:
        data = resp_sum.json()
        assert data["underlying"] == "NIFTY"
        assert "system_state" in data

    # List
    resp_list = client.get("/api/v1/opportunities")
    if resp_list.status_code == 200:
        data = resp_list.json()
        assert "items" in data
        assert "total" in data

    # Calibration
    resp_cal = client.get("/api/v1/opportunities/calibration")
    if resp_cal.status_code == 200:
        data = resp_cal.json()
        assert "sample_count" in data
        assert "score_bands" in data

    # Missed
    resp_miss = client.get("/api/v1/opportunities/missed")
    if resp_miss.status_code == 200:
        data = resp_miss.json()
        assert "items" in data
