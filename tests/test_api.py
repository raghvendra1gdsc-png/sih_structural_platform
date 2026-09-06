"""
tests/test_api.py
==================
Comprehensive integration and unit test suite for Phase 4 FastAPI backend.
Tests all REST endpoints, PostGIS spatial queries, GeoJSON map responses,
event summaries, time-series aggregations, and admin verification audit trails.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from backend.main import create_app
from backend.db.session import get_session
from backend.db.models import ReportORM, EarthquakeEventORM, VerificationAuditORM


@pytest.fixture(scope="module")
def client() -> TestClient:
    """FastAPI test client instance."""
    app = create_app()
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Health Endpoint Tests
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_healthz_connected(self, client: TestClient):
        """GET /healthz returns 200 with operational database and PostGIS status."""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["postgis"] is True
        assert data["postgis_version"] is not None
        assert "3.4" in data["postgis_version"] or "USE_GEOS" in data["postgis_version"]


# ---------------------------------------------------------------------------
# 2. Report Listing, Filtering & Single Report Tests
# ---------------------------------------------------------------------------

class TestReportEndpoints:
    def test_list_reports_default_pagination(self, client: TestClient):
        """GET /api/reports returns paginated items and total count."""
        response = client.get("/api/reports")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["limit"] == 50
        assert data["offset"] == 0
        assert data["total"] >= 50
        assert len(data["items"]) <= 50

    def test_list_reports_filter_by_event_id(self, client: TestClient):
        """GET /api/reports?event_id=... filters strictly by earthquake_event_id."""
        events_res = client.get("/api/events?limit=1")
        assert events_res.status_code == 200
        target_event_id = events_res.json()["items"][0]["event_id"]

        response = client.get(f"/api/reports?event_id={target_event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["earthquake_event_id"] == target_event_id

    def test_list_reports_filter_by_verification_status(self, client: TestClient):
        """GET /api/reports?verification_status=... filters by status."""
        response = client.get("/api/reports?verification_status=pending")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["verification_status"] == "pending"

    def test_list_reports_filter_by_damage_type(self, client: TestClient):
        """GET /api/reports?damage_type=structural_crack filters by damage type."""
        response = client.get("/api/reports?damage_type=structural_crack")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["damage_type"] == "structural_crack"

    def test_list_reports_filter_by_severity(self, client: TestClient):
        """GET /api/reports?damage_severity=moderate filters by severity."""
        response = client.get("/api/reports?damage_severity=moderate")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["severity"] == "moderate"

    def test_list_reports_filter_by_source_and_synthetic(self, client: TestClient):
        """GET /api/reports?source=synthetic&is_synthetic=true filters correctly."""
        response = client.get("/api/reports?source=synthetic&is_synthetic=true")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["source"] == "synthetic"
            assert item["is_synthetic"] is True

    def test_list_reports_date_range(self, client: TestClient):
        """GET /api/reports with date_from and date_to filters submitted_at."""
        response = client.get(
            "/api/reports?date_from=1990-01-01T00:00:00Z&date_to=2030-01-01T00:00:00Z"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0

    def test_list_reports_invalid_date_order(self, client: TestClient):
        """GET /api/reports with date_from > date_to returns 400."""
        response = client.get(
            "/api/reports?date_from=2030-01-01T00:00:00Z&date_to=2020-01-01T00:00:00Z"
        )
        assert response.status_code == 400

    def test_list_reports_pagination_clamping(self, client: TestClient):
        """Excessive limit above MAX_LIMIT (500) returns 422 validation error."""
        response = client.get("/api/reports?limit=1000")
        assert response.status_code == 422
        # Valid maximum limit returns 200
        response_max = client.get("/api/reports?limit=500")
        assert response_max.status_code == 200
        assert response_max.json()["limit"] == 500

    def test_list_reports_invalid_limit(self, client: TestClient):
        """Negative or zero limit returns 422."""
        response = client.get("/api/reports?limit=0")
        assert response.status_code == 422
        response_neg = client.get("/api/reports?limit=-10")
        assert response_neg.status_code == 422

    def test_get_single_report_success(self, client: TestClient):
        """GET /api/reports/{id} returns full report details."""
        list_res = client.get("/api/reports?limit=1")
        assert list_res.status_code == 200
        report_id = list_res.json()["items"][0]["report_id"]

        res = client.get(f"/api/reports/{report_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["report_id"] == report_id
        assert "latitude" in data
        assert "longitude" in data
        assert "damage_type" in data
        assert "severity" in data
        assert "verification_status" in data
        assert "is_synthetic" in data

    def test_get_single_report_not_found(self, client: TestClient):
        """GET /api/reports/{id} returns 404 for nonexistent UUID."""
        random_id = str(uuid.uuid4())
        res = client.get(f"/api/reports/{random_id}")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

    def test_get_single_report_invalid_uuid(self, client: TestClient):
        """GET /api/reports/{id} returns 422 for invalid UUID format."""
        res = client.get("/api/reports/not-a-valid-uuid")
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# 3. Geospatial PostGIS Search Tests
# ---------------------------------------------------------------------------

class TestGeospatialSearch:
    def test_nearby_reports_postgis_radius(self, client: TestClient):
        """GET /api/reports/nearby finds reports within PostGIS ST_DWithin radius."""
        # Find coordinates of an existing report to search around
        rep_res = client.get("/api/reports?limit=1")
        assert rep_res.status_code == 200
        sample_rep = rep_res.json()["items"][0]
        lat = sample_rep["latitude"]
        lon = sample_rep["longitude"]

        response = client.get(f"/api/reports/nearby?latitude={lat}&longitude={lon}&radius_km=100")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["radius_km"] == 100.0
        assert data["center_latitude"] == lat
        assert data["center_longitude"] == lon
        assert data["total"] >= 1

        # Check sorting by distance_km ascending
        distances = [item["distance_km"] for item in data["items"]]
        assert distances == sorted(distances)
        for item in data["items"]:
            assert item["distance_km"] <= 100.0
            assert item["distance_km"] >= 0.0

    def test_nearby_reports_invalid_radius(self, client: TestClient):
        """Validation fails for radius_km <= 0 or > 1000."""
        res_zero = client.get("/api/reports/nearby?latitude=23.4&longitude=70.2&radius_km=0")
        assert res_zero.status_code == 422
        res_neg = client.get("/api/reports/nearby?latitude=23.4&longitude=70.2&radius_km=-5")
        assert res_neg.status_code == 422
        res_huge = client.get("/api/reports/nearby?latitude=23.4&longitude=70.2&radius_km=1001")
        assert res_huge.status_code == 422

    def test_nearby_reports_invalid_coordinates(self, client: TestClient):
        """Validation fails for coordinates out of WGS84 range."""
        res_lat = client.get("/api/reports/nearby?latitude=95.0&longitude=70.2&radius_km=10")
        assert res_lat.status_code == 422
        res_lon = client.get("/api/reports/nearby?latitude=23.4&longitude=185.0&radius_km=10")
        assert res_lon.status_code == 422


# ---------------------------------------------------------------------------
# 4. Map GeoJSON Endpoint Tests
# ---------------------------------------------------------------------------

class TestMapEndpoint:
    def test_map_reports_valid_geojson(self, client: TestClient):
        """GET /api/map/reports returns valid RFC 7946 GeoJSON FeatureCollection."""
        response = client.get("/api/map/reports")
        assert response.status_code == 200
        geojson = response.json()
        assert geojson["type"] == "FeatureCollection"
        assert "features" in geojson
        assert isinstance(geojson["features"], list)
        assert len(geojson["features"]) > 0

        # Validate sample feature
        feature = geojson["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert len(feature["geometry"]["coordinates"]) == 2
        lon, lat = feature["geometry"]["coordinates"]
        assert -180.0 <= lon <= 180.0
        assert -90.0 <= lat <= 90.0

        # Validate lightweight properties (no bloated payloads)
        props = feature["properties"]
        assert "id" in props
        assert "damage_type" in props
        assert "severity" in props
        assert "verification_status" in props
        assert "source" in props
        assert "submitted_at" in props
        # Verify large raw text and embeddings are excluded
        assert "text" not in props
        assert "embedding" not in props

    def test_map_reports_filtering(self, client: TestClient):
        """GET /api/map/reports filters features by event_id."""
        events_res = client.get("/api/events?limit=1")
        assert events_res.status_code == 200
        target_event_id = events_res.json()["items"][0]["event_id"]

        response = client.get(f"/api/map/reports?event_id={target_event_id}")
        assert response.status_code == 200
        geojson = response.json()
        assert len(geojson["features"]) > 0


# ---------------------------------------------------------------------------
# 5. Earthquake Events Endpoint Tests
# ---------------------------------------------------------------------------

class TestEventEndpoints:
    def test_list_events(self, client: TestClient):
        """GET /api/events returns list of earthquake events."""
        response = client.get("/api/events")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_event_by_id_success(self, client: TestClient):
        """GET /api/events/{event_id} returns single event metadata."""
        events_res = client.get("/api/events?limit=1")
        assert events_res.status_code == 200
        sample_event = events_res.json()["items"][0]
        event_id = sample_event["event_id"]

        response = client.get(f"/api/events/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["event_id"] == event_id
        assert data["magnitude"] == sample_event["magnitude"]
        assert "latitude" in data
        assert "longitude" in data

    def test_get_event_by_id_not_found(self, client: TestClient):
        """GET /api/events/{event_id} returns 404 for nonexistent event."""
        response = client.get("/api/events/nonexistent_event_999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_event_summary_success(self, client: TestClient):
        """GET /api/events/{event_id}/summary returns aggregated impact metrics."""
        events_res = client.get("/api/events?limit=1")
        assert events_res.status_code == 200
        sample_event = events_res.json()["items"][0]
        event_id = sample_event["event_id"]

        response = client.get(f"/api/events/{event_id}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["event_id"] == event_id
        assert data["total_reports"] > 0
        assert data["verified_reports"] + data["pending_reports"] + data["rejected_reports"] == data["total_reports"]
        assert isinstance(data["damage_type_distribution"], dict)
        assert isinstance(data["severity_distribution"], dict)
        assert isinstance(data["source_distribution"], dict)
        assert "bounding_box" in data

    def test_get_event_summary_not_found(self, client: TestClient):
        """GET /api/events/{event_id}/summary returns 404 for nonexistent event."""
        response = client.get("/api/events/nonexistent_xyz/summary")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 6. Real-Time Database Statistics Tests
# ---------------------------------------------------------------------------

class TestStatsEndpoints:
    def test_stats_summary_database_derived(self, client: TestClient):
        """GET /api/stats/summary computes real aggregate statistics from SQL."""
        response = client.get("/api/stats/summary")
        assert response.status_code == 200
        data = response.json()

        # Check report counts consistency
        assert data["total_reports"] >= 50
        assert data["canonical_reports"] + data["duplicate_reports"] == data["total_reports"]
        assert (
            data["verified_reports"] + data["pending_reports"] + data["rejected_reports"]
            == data["total_reports"]
        )
        assert data["synthetic_reports"] + data["real_reports"] == data["total_reports"]

        # Check distribution mappings
        assert isinstance(data["damage_type_counts"], dict)
        assert sum(data["damage_type_counts"].values()) == data["total_reports"]

        assert isinstance(data["severity_counts"], dict)
        assert sum(data["severity_counts"].values()) == data["total_reports"]

        assert isinstance(data["source_counts"], dict)
        assert sum(data["source_counts"].values()) == data["total_reports"]

        assert isinstance(data["event_counts"], dict)
        assert len(data["event_counts"]) > 0

    def test_stats_timeline_day(self, client: TestClient):
        """GET /api/stats/timeline?interval=day aggregates time-series."""
        response = client.get("/api/stats/timeline?interval=day")
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "day"
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0
        for pt in data["data"]:
            assert "date" in pt
            assert "count" in pt
            assert pt["count"] >= 1

    def test_stats_timeline_hour_and_week(self, client: TestClient):
        """GET /api/stats/timeline supports hour and week intervals."""
        res_hour = client.get("/api/stats/timeline?interval=hour")
        assert res_hour.status_code == 200
        assert res_hour.json()["interval"] == "hour"

        res_week = client.get("/api/stats/timeline?interval=week")
        assert res_week.status_code == 200
        assert res_week.json()["interval"] == "week"

    def test_stats_timeline_invalid_interval(self, client: TestClient):
        """Unsupported interval returns 422."""
        response = client.get("/api/stats/timeline?interval=decade")
        assert response.status_code == 422

    def test_stats_timeline_invalid_date_order(self, client: TestClient):
        """date_from after date_to returns 400 Bad Request."""
        response = client.get(
            "/api/stats/timeline?date_from=2026-01-01T00:00:00Z&date_to=2025-01-01T00:00:00Z"
        )
        assert response.status_code == 400
        assert "date_from must be before or equal to date_to" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 7. Admin Verification & Audit Log Tests
# ---------------------------------------------------------------------------

class TestAdminEndpoints:
    def test_get_pending_reports(self, client: TestClient):
        """GET /api/admin/reports/pending returns reports needing review."""
        response = client.get("/api/admin/reports/pending")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        for item in data["items"]:
            assert item["verification_status"] == "pending"

    def test_admin_approve_and_audit(self, client: TestClient):
        """PATCH /api/admin/reports/{id}/verification approves report and records audit."""
        # Find a report to test approval
        rep_res = client.get("/api/reports?limit=1")
        report_id = rep_res.json()["items"][0]["report_id"]

        action_payload = {
            "action": "approve",
            "reason": "Test approval verification by structural engineer",
        }
        res = client.patch(f"/api/admin/reports/{report_id}/verification", json=action_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["report_id"] == report_id
        assert data["new_status"] == "verified"
        assert data["action"] == "approve"
        assert data["audit_id"] is not None

        # Verify audit record is queryable
        audit_res = client.get(f"/api/admin/audits?report_id={report_id}")
        assert audit_res.status_code == 200
        audits = audit_res.json()
        assert audits["total"] >= 1
        actions = [a["action"] for a in audits["items"]]
        assert "approve" in actions

    def test_admin_reject_and_audit(self, client: TestClient):
        """PATCH /api/admin/reports/{id}/verification rejects report and records audit."""
        rep_res = client.get("/api/reports?limit=1")
        report_id = rep_res.json()["items"][0]["report_id"]

        action_payload = {
            "action": "reject",
            "reason": "False alarm or non-earthquake structural damage",
        }
        res = client.patch(f"/api/admin/reports/{report_id}/verification", json=action_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["report_id"] == report_id
        assert data["new_status"] == "rejected"
        assert data["action"] == "reject"

    def test_admin_merge_and_audit(self, client: TestClient):
        """PATCH /api/admin/reports/{id}/verification merges report into canonical."""
        # Get two distinct reports
        rep_res = client.get("/api/reports?limit=2")
        items = rep_res.json()["items"]
        assert len(items) >= 2
        canonical_id = items[0]["report_id"]
        duplicate_id = items[1]["report_id"]

        merge_payload = {
            "action": "merge",
            "duplicate_of": canonical_id,
            "reason": "Identified as duplicate observation of same building collapse",
        }
        res = client.patch(f"/api/admin/reports/{duplicate_id}/verification", json=merge_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["report_id"] == duplicate_id
        assert data["action"] == "merge"
        assert data["duplicate_of"] == canonical_id
        assert data["new_status"] == "verified"

        # Verify the duplicate report still exists (raw evidence NEVER deleted)
        verify_res = client.get(f"/api/reports/{duplicate_id}")
        assert verify_res.status_code == 200
        assert verify_res.json()["duplicate_of"] == canonical_id

    def test_admin_merge_validation_errors(self, client: TestClient):
        """Merge action fails with appropriate 400/404 errors for invalid payloads."""
        rep_res = client.get("/api/reports?limit=1")
        report_id = rep_res.json()["items"][0]["report_id"]

        # Missing duplicate_of
        res_missing = client.patch(
            f"/api/admin/reports/{report_id}/verification",
            json={"action": "merge", "reason": "No target"},
        )
        assert res_missing.status_code == 400
        assert "duplicate_of" in res_missing.json()["detail"].lower() or "canonical_report_id" in res_missing.json()["detail"].lower()

        # Merge into self
        res_self = client.patch(
            f"/api/admin/reports/{report_id}/verification",
            json={"action": "merge", "duplicate_of": report_id, "reason": "Self target"},
        )
        assert res_self.status_code == 400
        assert "cannot merge a report into itself" in res_self.json()["detail"].lower()

        # Merge into nonexistent canonical report
        fake_id = str(uuid.uuid4())
        res_fake = client.patch(
            f"/api/admin/reports/{report_id}/verification",
            json={"action": "merge", "duplicate_of": fake_id, "reason": "Fake target"},
        )
        assert res_fake.status_code == 404
        assert "target canonical report" in res_fake.json()["detail"].lower()

    def test_admin_audits_endpoint_pagination(self, client: TestClient):
        """GET /api/admin/audits returns paginated audit events."""
        response = client.get("/api/admin/audits?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert data["total"] >= 1
