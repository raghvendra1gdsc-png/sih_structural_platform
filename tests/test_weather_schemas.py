"""
tests/test_weather_schemas.py
=============================
Unit tests for National Weather Big Data Analytics Platform Pydantic v2 schemas.
Exercises valid and invalid fixtures, boundaries, defaults, and serializations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from ingestion.weather_schemas import (
    WeatherEventCategory,
    WeatherReportSource,
    VerificationStatus,
    SeverityLevel,
    RawWeatherReport,
    NormalizedWeatherReport,
    WeatherIncidentSchema,
    OpenMeteoCurrent,
    OpenMeteoResponse,
)


class TestWeatherEnums:
    def test_weather_event_category_graceful_missing(self):
        """Variant casing and delimiters should map to canonical categories."""
        assert WeatherEventCategory("rainfall") == WeatherEventCategory.rainfall
        assert WeatherEventCategory("RAIN-FALL") == WeatherEventCategory.rainfall
        assert WeatherEventCategory("dust storm") == WeatherEventCategory.dust_storm
        assert WeatherEventCategory("DUST_STORM") == WeatherEventCategory.dust_storm
        assert WeatherEventCategory("unrecognized_event_type") == WeatherEventCategory.other

    def test_enum_members_completeness(self):
        assert WeatherEventCategory.flooding.value == "flooding"
        assert WeatherEventCategory.thunderstorm.value == "thunderstorm"
        assert WeatherEventCategory.heatwave.value == "heatwave"
        assert WeatherEventCategory.cyclone.value == "cyclone"
        assert WeatherEventCategory.hailstorm.value == "hailstorm"
        assert WeatherEventCategory.lightning.value == "lightning"
        assert WeatherEventCategory.fog.value == "fog"
        assert WeatherEventCategory.cold_wave.value == "cold_wave"
        assert WeatherEventCategory.landslide.value == "landslide"


class TestRawWeatherReport:
    def test_valid_with_coordinates(self):
        report = RawWeatherReport(
            source=WeatherReportSource.citizen,
            latitude=26.9124,
            longitude=75.7873,
            city="Jaipur",
            state="Rajasthan",
            text="Intense sudden downpour causing street flooding in MI Road.",
            is_synthetic=True,
        )
        assert isinstance(report.report_id, uuid.UUID)
        assert report.city == "Jaipur"
        assert report.latitude == 26.9124
        assert report.is_synthetic is True

    def test_valid_with_text_location_only(self):
        """Location validator passes if text location (city/state) is present even without coords."""
        report = RawWeatherReport(
            source=WeatherReportSource.citizen,
            city="Mumbai",
            state="Maharashtra",
            text="High water logging near Hindmata cinema.",
        )
        assert report.city == "Mumbai"
        assert report.latitude is None

    def test_invalid_missing_all_locations(self):
        """Should fail validation if neither coordinates nor city/state are provided."""
        with pytest.raises(ValidationError) as excinfo:
            RawWeatherReport(
                source=WeatherReportSource.citizen,
                text="Heavy rain outside.",
                city=None,
                state=None,
                district=None,
                latitude=None,
                longitude=None,
            )
        assert "Report must contain either coordinates or a recognizable location" in str(excinfo.value)

    def test_invalid_lat_lon_bounds(self):
        with pytest.raises(ValidationError):
            RawWeatherReport(
                city="Delhi",
                latitude=95.0,  # Invalid > 90
                longitude=77.1025,
            )

        with pytest.raises(ValidationError):
            RawWeatherReport(
                city="Delhi",
                latitude=28.7041,
                longitude=195.0,  # Invalid > 180
            )


class TestNormalizedWeatherReport:
    def test_valid_normalized_report(self):
        now = datetime.now(timezone.utc)
        report = NormalizedWeatherReport(
            source=WeatherReportSource.synthetic,
            submitted_at=now,
            event_time=now,
            city="Chennai",
            state="Tamil Nadu",
            latitude=13.0827,
            longitude=80.2707,
            text="Continuous water stagnation near T Nagar.",
            event_category=WeatherEventCategory.flooding,
            event_confidence=0.92,
            source_trust_score=78.5,
            misinformation_score=10.0,
            verification_status=VerificationStatus.pending,
            is_synthetic=True,
        )
        assert report.city == "Chennai"
        assert report.event_category == WeatherEventCategory.flooding
        assert report.source_trust_score == 78.5
        assert report.verification_status == VerificationStatus.pending

    def test_trust_score_bounds(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            NormalizedWeatherReport(
                source=WeatherReportSource.citizen,
                submitted_at=now,
                event_time=now,
                city="Kolkata",
                state="West Bengal",
                latitude=22.5726,
                longitude=88.3639,
                source_trust_score=105.0,  # Invalid > 100
            )


class TestWeatherIncidentSchema:
    def test_valid_incident(self):
        now = datetime.now(timezone.utc)
        incident = WeatherIncidentSchema(
            event_category=WeatherEventCategory.rainfall,
            centroid_lat=28.6139,
            centroid_lon=77.2090,
            start_time=now,
            end_time=now,
            report_count=12,
            verified_count=4,
            severity=SeverityLevel.high,
            impact_score=82.0,
            confidence=0.89,
            city="Delhi",
            state="Delhi",
            radius_km=4.5,
            summary="Multiple reports of water logging and severe traffic stagnation.",
        )
        assert incident.report_count == 12
        assert incident.severity == SeverityLevel.high
        assert incident.impact_score == 82.0


class TestOpenMeteoSchemas:
    def test_open_meteo_serialization(self):
        payload = {
            "latitude": 26.91,
            "longitude": 75.78,
            "timezone": "Asia/Kolkata",
            "current": {
                "time": "2026-09-04T12:00",
                "temperature_2m": 32.5,
                "relative_humidity_2m": 68.0,
                "precipitation": 14.2,
                "weather_code": 65,
                "wind_speed_10m": 18.5,
            },
        }
        resp = OpenMeteoResponse.model_validate(payload)
        assert resp.latitude == 26.91
        assert resp.current is not None
        assert resp.current.temperature_2m == 32.5
        assert resp.current.precipitation == 14.2
        assert resp.current.weather_code == 65
