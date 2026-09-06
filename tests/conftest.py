"""
tests/conftest.py
=================
Shared pytest fixtures for Phase 0/1 tests.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingestion.schemas import (
    EarthquakeEvent,
    GeographicScope,
    MagnitudeType,
    RawReport,
    ReportSource,
)

# ---------------------------------------------------------------------------
# Minimal fixture earthquake events
# ---------------------------------------------------------------------------

@pytest.fixture
def chamoli_event() -> EarthquakeEvent:
    """A real Tier 1 (india) event — 1999 Chamoli earthquake."""
    return EarthquakeEvent(
        event_id="usp0009hkv",
        magnitude=6.6,
        magnitude_type=MagnitudeType.mw,
        latitude=30.408,
        longitude=79.416,
        depth_km=15.0,
        place="Chamoli, Uttarakhand, India",
        event_time=datetime(1999, 3, 29, 0, 35, 3, tzinfo=timezone.utc),
        url="https://earthquake.usgs.gov/earthquakes/eventpage/usp0009hkv",
        geographic_scope=GeographicScope.india,
    )


@pytest.fixture
def nepal_event() -> EarthquakeEvent:
    """A real Tier 2 (regional) event — 2015 Nepal earthquake."""
    return EarthquakeEvent(
        event_id="us20002926",
        magnitude=7.8,
        magnitude_type=MagnitudeType.mww,
        latitude=28.2305,
        longitude=84.7314,
        depth_km=8.22,
        place="34 km E of Lamjung, Nepal",
        event_time=datetime(2015, 4, 25, 6, 11, 26, tzinfo=timezone.utc),
        url="https://earthquake.usgs.gov/earthquakes/eventpage/us20002926",
        geographic_scope=GeographicScope.regional,
    )


@pytest.fixture
def minimal_raw_report(chamoli_event) -> RawReport:
    """Minimal valid synthetic RawReport."""
    return RawReport(
        source=ReportSource.synthetic,
        submitted_at=datetime(1999, 3, 29, 2, 0, 0, tzinfo=timezone.utc),
        latitude=30.41,
        longitude=79.42,
        location_text="Chamoli district, Uttarakhand",
        text="Cracks appeared in the walls after the earthquake.",
        earthquake_event_id=chamoli_event.event_id,
        is_synthetic=True,
    )


@pytest.fixture
def usgs_cache_path(tmp_path) -> Path:
    """Temporary USGS cache file with two real events."""
    cache = [
        {
            "event_id": "usp0009hkv",
            "magnitude": 6.6,
            "magnitude_type": "mw",
            "latitude": 30.408,
            "longitude": 79.416,
            "depth_km": 15.0,
            "place": "Chamoli, Uttarakhand, India",
            "event_time": "1999-03-29T00:35:03+00:00",
            "url": "https://earthquake.usgs.gov/earthquakes/eventpage/usp0009hkv",
            "geographic_scope": "india",
        },
        {
            "event_id": "us20002926",
            "magnitude": 7.8,
            "magnitude_type": "mww",
            "latitude": 28.2305,
            "longitude": 84.7314,
            "depth_km": 8.22,
            "place": "34 km E of Lamjung, Nepal",
            "event_time": "2015-04-25T06:11:26+00:00",
            "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us20002926",
            "geographic_scope": "regional",
        },
    ]
    p = tmp_path / "usgs_cache.json"
    p.write_text(json.dumps(cache), encoding="utf-8")
    return p
