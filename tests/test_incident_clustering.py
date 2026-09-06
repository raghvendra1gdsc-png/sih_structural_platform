"""
tests/test_incident_clustering.py
=================================
Unit tests for geospatial incident clustering and Platform Impact Scoring.
Verifies spatiotemporal grouping, centroid calculations, and impact score severity boundaries.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
import pytest

from ingestion.weather_schemas import (
    NormalizedWeatherReport,
    WeatherReportSource,
    WeatherEventCategory,
    SeverityLevel,
    VerificationStatus,
)
from ml_pipeline.incident_clustering import (
    IncidentClusteringEngine,
    calculate_platform_impact_score,
)


def test_calculate_platform_impact_score_severities():
    # Low severity scenario: 1 report, low hazard category, low velocity
    score_low, sev_low = calculate_platform_impact_score(
        report_count=1,
        verified_count=0,
        category=WeatherEventCategory.fog,
        radius_km=2.0,
        reports_per_hour=0.5,
    )
    assert sev_low == SeverityLevel.low
    assert score_low <= 25.0

    # High / Severe scenario: 25 reports, 15 verified, cyclone, high velocity
    score_severe, sev_severe = calculate_platform_impact_score(
        report_count=25,
        verified_count=15,
        category=WeatherEventCategory.cyclone,
        radius_km=15.0,
        reports_per_hour=10.0,
    )
    assert sev_severe == SeverityLevel.severe
    assert score_severe > 75.0


def test_cluster_multiple_reports_same_city():
    engine = IncidentClusteringEngine(cluster_distance_km=12.0, cluster_window_minutes=240.0)
    now = datetime.now(timezone.utc)

    # 3 reports in Mumbai within 3 km of each other
    reports = [
        NormalizedWeatherReport(
            report_id=uuid.uuid4(),
            source=WeatherReportSource.citizen,
            submitted_at=now,
            event_time=now,
            city="Mumbai",
            state="Maharashtra",
            latitude=19.0760,
            longitude=72.8777,
            text="Flooding at Hindmata",
            event_category=WeatherEventCategory.flooding,
            verification_status=VerificationStatus.verified,
        ),
        NormalizedWeatherReport(
            report_id=uuid.uuid4(),
            source=WeatherReportSource.citizen,
            submitted_at=now + timedelta(minutes=20),
            event_time=now + timedelta(minutes=20),
            city="Mumbai",
            state="Maharashtra",
            latitude=19.0800,
            longitude=72.8800,
            text="Underpass submerged in Dadar",
            event_category=WeatherEventCategory.flooding,
            verification_status=VerificationStatus.verified,
        ),
        NormalizedWeatherReport(
            report_id=uuid.uuid4(),
            source=WeatherReportSource.citizen,
            submitted_at=now + timedelta(minutes=45),
            event_time=now + timedelta(minutes=45),
            city="Mumbai",
            state="Maharashtra",
            latitude=19.0720,
            longitude=72.8750,
            text="Traffic halted due to high water levels",
            event_category=WeatherEventCategory.flooding,
            verification_status=VerificationStatus.pending,
        ),
    ]

    incidents = engine.cluster_reports(reports)
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.city == "Mumbai"
    assert inc.report_count == 3
    assert inc.verified_count == 2
    assert inc.event_category == WeatherEventCategory.flooding
    # Centroid should be within the cluster bounds
    assert 19.070 <= inc.centroid_lat <= 19.085
    assert 72.870 <= inc.centroid_lon <= 72.885


def test_cluster_filters_duplicates():
    engine = IncidentClusteringEngine()
    now = datetime.now(timezone.utc)
    canon_id = uuid.uuid4()

    canonical = NormalizedWeatherReport(
        report_id=canon_id,
        source=WeatherReportSource.citizen,
        submitted_at=now,
        event_time=now,
        city="Delhi",
        state="Delhi",
        latitude=28.6139,
        longitude=77.2090,
        text="Rain in CP",
        event_category=WeatherEventCategory.rainfall,
        duplicate_of=None,
    )

    duplicate = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now,
        event_time=now,
        city="Delhi",
        state="Delhi",
        latitude=28.6140,
        longitude=77.2091,
        text="Rain in CP",
        event_category=WeatherEventCategory.rainfall,
        duplicate_of=canon_id,  # Marked duplicate
    )

    incidents = engine.cluster_reports([canonical, duplicate])
    # Only the canonical report is clustered into the incident
    assert len(incidents) == 1
    assert incidents[0].report_count == 1
