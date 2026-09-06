"""
tests/test_weather_dedup.py
===========================
Unit tests for the WeatherDeduplicationEngine.
Tests spatial, temporal, category, and textual similarity deduplication.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
import pytest

from ingestion.weather_schemas import (
    NormalizedWeatherReport,
    WeatherReportSource,
    WeatherEventCategory,
    VerificationStatus,
)
from ml_pipeline.weather_dedup import (
    WeatherDeduplicationEngine,
    haversine_distance_km,
    text_token_similarity,
)


def test_haversine_distance():
    # Same point -> 0 km
    assert haversine_distance_km(26.9124, 75.7873, 26.9124, 75.7873) == pytest.approx(0.0, abs=1e-3)
    # Delhi (28.6139, 77.2090) to Jaipur (26.9124, 75.7873) is ~235-245 km
    dist = haversine_distance_km(28.6139, 77.2090, 26.9124, 75.7873)
    assert 230.0 < dist < 250.0


def test_text_token_similarity():
    # Identical text
    assert text_token_similarity("Heavy rain in Connaught Place", "Heavy rain in Connaught Place") == 1.0
    # Completely disjoint
    assert text_token_similarity("Sunny hot afternoon", "Freezing winter blizzard") == 0.0
    # Partial overlap
    sim = text_token_similarity("Severe waterlogging on Ring Road", "Waterlogging and traffic jam on Ring Road")
    assert 0.3 < sim < 0.9


def test_dedup_nearby_coincident_reports():
    engine = WeatherDeduplicationEngine(spatial_threshold_km=3.5, temporal_threshold_mins=90.0)
    now = datetime.now(timezone.utc)

    canonical = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now,
        event_time=now,
        city="Mumbai",
        state="Maharashtra",
        latitude=19.0760,
        longitude=72.8777,
        text="Heavy water logging at Hindmata cinema junction, vehicles stranded.",
        event_category=WeatherEventCategory.flooding,
    )

    # Candidate 0.8 km away, 15 mins later, similar flooding report
    candidate = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now + timedelta(minutes=15),
        event_time=now + timedelta(minutes=15),
        city="Mumbai",
        state="Maharashtra",
        latitude=19.0810,
        longitude=72.8790,
        text="Water logging around Hindmata junction, roads flooded.",
        event_category=WeatherEventCategory.flooding,
    )

    decision = engine.compare_reports(candidate, canonical)
    assert decision.is_duplicate is True
    assert decision.canonical_id == canonical.report_id
    assert decision.duplicate_score >= 60.0


def test_dedup_distant_reports_not_duplicate():
    engine = WeatherDeduplicationEngine(spatial_threshold_km=3.5, temporal_threshold_mins=90.0)
    now = datetime.now(timezone.utc)

    canonical = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now,
        event_time=now,
        city="Delhi",
        state="Delhi",
        latitude=28.6139,
        longitude=77.2090,
        text="Rain in Central Delhi.",
        event_category=WeatherEventCategory.rainfall,
    )

    # 15 km away -> outside spatial threshold
    candidate = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now + timedelta(minutes=5),
        event_time=now + timedelta(minutes=5),
        city="Delhi",
        state="Delhi",
        latitude=28.7500,
        longitude=77.1000,
        text="Rain in North Delhi.",
        event_category=WeatherEventCategory.rainfall,
    )

    decision = engine.compare_reports(candidate, canonical)
    assert decision.is_duplicate is False
    assert decision.canonical_id is None


def test_dedup_time_separated_reports_not_duplicate():
    engine = WeatherDeduplicationEngine(spatial_threshold_km=3.5, temporal_threshold_mins=90.0)
    now = datetime.now(timezone.utc)

    canonical = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now,
        event_time=now,
        city="Jaipur",
        state="Rajasthan",
        latitude=26.9124,
        longitude=75.7873,
        text="Dust storm blowing across the city.",
        event_category=WeatherEventCategory.dust_storm,
    )

    # 4 hours later -> outside temporal window
    candidate = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now + timedelta(hours=4),
        event_time=now + timedelta(hours=4),
        city="Jaipur",
        state="Rajasthan",
        latitude=26.9124,
        longitude=75.7873,
        text="Dust storm blowing across the city.",
        event_category=WeatherEventCategory.dust_storm,
    )

    decision = engine.compare_reports(candidate, canonical)
    assert decision.is_duplicate is False


def test_dedup_category_mismatch():
    engine = WeatherDeduplicationEngine(spatial_threshold_km=3.5, temporal_threshold_mins=90.0)
    now = datetime.now(timezone.utc)

    canonical = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now,
        event_time=now,
        city="Jaipur",
        state="Rajasthan",
        latitude=26.9124,
        longitude=75.7873,
        text="Extreme heatwave at noon.",
        event_category=WeatherEventCategory.heatwave,
    )

    candidate = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now,
        event_time=now,
        city="Jaipur",
        state="Rajasthan",
        latitude=26.9124,
        longitude=75.7873,
        text="Sudden hailstorm pellets falling.",
        event_category=WeatherEventCategory.hailstorm,
    )

    decision = engine.compare_reports(candidate, canonical)
    assert decision.is_duplicate is False


def test_batch_dedup_processing():
    engine = WeatherDeduplicationEngine()
    now = datetime.now(timezone.utc)

    rep1 = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now,
        event_time=now,
        city="Bengaluru",
        state="Karnataka",
        latitude=12.9716,
        longitude=77.5946,
        text="Heavy thunderstorm in Indiranagar.",
        event_category=WeatherEventCategory.thunderstorm,
    )

    rep2 = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now + timedelta(minutes=10),
        event_time=now + timedelta(minutes=10),
        city="Bengaluru",
        state="Karnataka",
        latitude=12.9720,
        longitude=77.5950,
        text="Thunderstorm and lightning in Indiranagar.",
        event_category=WeatherEventCategory.thunderstorm,
    )

    batch = engine.process_batch([rep1, rep2])
    assert len(batch) == 2
    assert batch[0].duplicate_of is None
    assert batch[1].duplicate_of == batch[0].report_id
