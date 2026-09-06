"""
tests/test_weather_api.py
=========================
Integration tests for the National Weather Big Data Analytics Platform REST API.
Tests all critical routes against the running backend and database:
- GET /healthz
- GET /api/system/health
- GET /api/weather/current
- GET /api/stats/summary
- GET /api/stats/by-category
- GET /api/reports
- GET /api/incidents
- GET /api/map/incidents
- GET /api/map/reports
- POST /api/chat/weathergpt
- PATCH /api/admin/reports/{id}/verify
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_healthz(client: TestClient):
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_system_health(client: TestClient):
    response = client.get("/api/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["database"] in ("connected", "unavailable")


def test_current_weather(client: TestClient):
    response = client.get("/api/weather/current?city=Jaipur")
    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "Jaipur"
    assert "temperature_c" in data
    assert "wind_kmh" in data


def test_stats_summary(client: TestClient):
    response = client.get("/api/stats/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_reports" in data
    assert "verified_reports" in data
    assert "unique_incidents" in data
    assert "states_affected" in data


def test_stats_by_category(client: TestClient):
    response = client.get("/api/stats/by-category")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_reports_paginated(client: TestClient):
    response = client.get("/api/reports?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    if len(data["items"]) > 0:
        rep = data["items"][0]
        assert "report_id" in rep
        assert "city" in rep
        assert "event_category" in rep
        assert "source_trust_score" in rep


def test_get_incidents_paginated(client: TestClient):
    response = client.get("/api/incidents?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    if len(data["items"]) > 0:
        inc = data["items"][0]
        assert "incident_id" in inc
        assert "city" in inc
        assert "impact_score" in inc
        assert "severity" in inc


def test_map_endpoints_geojson(client: TestClient):
    resp_inc = client.get("/api/map/incidents")
    assert resp_inc.status_code == 200
    inc_data = resp_inc.json()
    assert inc_data["type"] == "FeatureCollection"
    assert isinstance(inc_data["features"], list)

    resp_rep = client.get("/api/map/reports")
    assert resp_rep.status_code == 200
    rep_data = resp_rep.json()
    assert rep_data["type"] == "FeatureCollection"
    assert isinstance(rep_data["features"], list)


def test_weather_gpt_endpoint(client: TestClient):
    payload = {
        "query": "Will it rain in Delhi tomorrow? Should I carry an umbrella?",
        "city": "Delhi",
    }
    response = client.post("/api/chat/weathergpt", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "Delhi"
    assert "answer" in data
    assert len(data["citations"]) > 0
    assert "structured_context" in data


def test_admin_verification_flow(client: TestClient):
    # Fetch a pending report
    resp_list = client.get("/api/reports?verification_status=pending&limit=1")
    assert resp_list.status_code == 200
    reports = resp_list.json().get("items", [])
    if reports:
        target_id = reports[0]["report_id"]
        # Verify report
        patch_resp = client.patch(
            f"/api/admin/reports/{target_id}/verify",
            json={"status": "verified", "admin_notes": "Verified via radar overlay in test"},
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["verification_status"] == "verified"
