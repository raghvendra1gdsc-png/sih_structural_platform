"""
tests/test_trust_engine.py
==========================
Unit tests for the SourceTrustEngine and explainable misinformation triage.
Verifies transparent scoring, breakdown calculation, corroboration bonuses, and explainability tags.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
import pytest

from ingestion.weather_schemas import (
    NormalizedWeatherReport,
    WeatherReportSource,
    WeatherEventCategory,
)
from ml_pipeline.trust_engine import SourceTrustEngine, DEFAULT_TRUST_ENGINE


@pytest.fixture
def trust_engine() -> SourceTrustEngine:
    return SourceTrustEngine()


def test_high_trust_corroborated_report(trust_engine: SourceTrustEngine):
    now = datetime.now(timezone.utc)
    report = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.weather_api,
        submitted_at=now,
        event_time=now,
        city="Mumbai",
        state="Maharashtra",
        latitude=19.0760,
        longitude=72.8777,
        text="Automatic weather station heavy rainfall alert: 45mm in past hour.",
        event_category=WeatherEventCategory.rainfall,
        media_urls=["https://assets.met.gov.in/radar/mumbai_current.png"],
    )

    evaluation = trust_engine.evaluate(
        report=report,
        forecast_condition="heavy rain showers",
        forecast_precipitation_prob=95.0,
        nearby_reports_count=8,
    )

    assert evaluation.trust_score >= 85.0
    assert evaluation.misinformation_score <= 15.0
    assert evaluation.is_credible is True
    # Breakdown keys exist and sum up
    assert sum(evaluation.breakdown.values()) == pytest.approx(evaluation.trust_score, abs=0.1)
    # Reasons contain checkmarks
    assert any("✓" in r for r in evaluation.reasons)


def test_low_trust_conflicting_isolated_report(trust_engine: SourceTrustEngine):
    now = datetime.now(timezone.utc)
    report = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now,
        event_time=now,
        city="Jodhpur",
        state="Rajasthan",
        latitude=26.2389,
        longitude=73.0243,
        text="Massive flood wave sweeping through the streets.",
        event_category=WeatherEventCategory.flooding,
        media_urls=[],  # No evidence
    )

    evaluation = trust_engine.evaluate(
        report=report,
        forecast_condition="clear sunny dry",
        forecast_precipitation_prob=0.0,
        nearby_reports_count=0,  # Isolated
    )

    # Trust score should be penalized for conflicting forecast, isolation, and no media
    assert evaluation.trust_score < 60.0
    assert evaluation.misinformation_score > 40.0
    # Must contain warning explanations
    assert any("⚠ Conflicting observation" in r for r in evaluation.reasons)
    assert any("⚠ Isolated report" in r for r in evaluation.reasons)


def test_outside_geographic_bounds_penalty(trust_engine: SourceTrustEngine):
    now = datetime.now(timezone.utc)
    report = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=now,
        event_time=now,
        city="FarAway",
        state="Unknown",
        latitude=55.7558,  # Moscow, Russia coords
        longitude=37.6173,
        text="Heavy rain here.",
        event_category=WeatherEventCategory.rainfall,
    )

    evaluation = trust_engine.evaluate(report=report)
    assert evaluation.breakdown["spatial_consistency"] < 10.0
    assert any("⚠ Coordinates fall outside verified national geographic boundaries" in r for r in evaluation.reasons)


def test_stale_timestamp_penalty(trust_engine: SourceTrustEngine):
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(days=5)  # 120 hours old
    report = NormalizedWeatherReport(
        report_id=uuid.uuid4(),
        source=WeatherReportSource.citizen,
        submitted_at=stale_time,
        event_time=stale_time,
        city="Delhi",
        state="Delhi",
        latitude=28.6139,
        longitude=77.2090,
        text="Fog this morning.",
        event_category=WeatherEventCategory.fog,
    )

    evaluation = trust_engine.evaluate(report=report)
    assert evaluation.breakdown["temporal_consistency"] < 12.0
    assert any("⚠ Historical record submitted" in r for r in evaluation.reasons)
