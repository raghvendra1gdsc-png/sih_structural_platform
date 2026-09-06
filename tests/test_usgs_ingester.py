"""
tests/test_usgs_ingester.py
============================
Tests for the USGS ingestion module (Phase 1).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ingestion.schemas import EarthquakeEvent, GeographicScope, MagnitudeType
from ingestion.usgs_ingester import (
    DataSourceUnavailableError,
    classify_geographic_scope,
    fetch_usgs_events,
    load_cached_events,
    save_events_to_cache,
    select_events_for_demo,
)

# ---------------------------------------------------------------------------
# Geographic classification
# ---------------------------------------------------------------------------

class TestGeographicClassification:
    def test_chamoli_india(self):
        scope = classify_geographic_scope(30.408, 79.416, "Chamoli, Uttarakhand, India")
        assert scope == GeographicScope.india

    def test_bhuj_india_by_place(self):
        scope = classify_geographic_scope(23.6, 70.0, "Bhuj, Gujarat, India")
        assert scope == GeographicScope.india

    def test_india_inside_bbox(self):
        """Coordinates clearly inside India — no keyword needed."""
        scope = classify_geographic_scope(22.5, 80.0, "Central India region")
        # "India" keyword in place makes this Tier 1
        assert scope == GeographicScope.india

    def test_nepal_regional(self):
        scope = classify_geographic_scope(28.23, 84.73, "34 km E of Lamjung, Nepal")
        assert scope == GeographicScope.regional

    def test_afghanistan_regional(self):
        scope = classify_geographic_scope(36.0, 70.0, "Hindu Kush, Afghanistan")
        assert scope == GeographicScope.regional

    def test_myanmar_regional(self):
        scope = classify_geographic_scope(20.0, 96.0, "Sagaing, Myanmar")
        assert scope == GeographicScope.regional

    def test_china_qinghai_regional(self):
        scope = classify_geographic_scope(35.9, 90.5, "Southern Qinghai, China")
        assert scope == GeographicScope.regional

    def test_japan_other(self):
        scope = classify_geographic_scope(35.7, 139.6, "Tokyo, Japan")
        assert scope == GeographicScope.other

    def test_california_other(self):
        scope = classify_geographic_scope(34.0, -118.0, "Los Angeles, California")
        assert scope == GeographicScope.other

    def test_empty_place_falls_back_to_coords(self):
        """No keywords — classification relies on coordinates alone."""
        # In Indian bbox
        scope = classify_geographic_scope(20.0, 78.0, "")
        assert scope == GeographicScope.india  # inside India bbox

    def test_andaman_india(self):
        """Andaman Islands should be classified as India (in bbox)."""
        scope = classify_geographic_scope(12.0, 92.7, "Andaman and Nicobar Islands, India")
        assert scope == GeographicScope.india


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

class TestCacheHelpers:
    def test_load_cache_returns_none_when_absent(self, tmp_path):
        p = tmp_path / "nonexistent.json"
        result = load_cached_events(p)
        assert result is None

    def test_save_and_load_roundtrip(self, tmp_path, chamoli_event, nepal_event):
        p = tmp_path / "cache.json"
        events = [chamoli_event, nepal_event]
        save_events_to_cache(events, p)
        loaded = load_cached_events(p)
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0].event_id == chamoli_event.event_id
        assert loaded[1].event_id == nepal_event.event_id

    def test_load_corrupt_cache_returns_none(self, tmp_path):
        p = tmp_path / "cache.json"
        p.write_text("NOT VALID JSON {{{")
        result = load_cached_events(p)
        assert result is None

    def test_geographic_scope_preserved_in_cache(self, tmp_path, chamoli_event):
        p = tmp_path / "cache.json"
        save_events_to_cache([chamoli_event], p)
        loaded = load_cached_events(p)
        assert loaded[0].geographic_scope == GeographicScope.india


# ---------------------------------------------------------------------------
# fetch_usgs_events (mocked network)
# ---------------------------------------------------------------------------

_VALID_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "usp0009hkv",
            "properties": {
                "mag": 6.6,
                "magType": "mw",
                "place": "Chamoli, Uttarakhand, India",
                "time": 922578903000,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/usp0009hkv",
            },
            "geometry": {"type": "Point", "coordinates": [79.416, 30.408, 15.0]},
        },
        {
            "type": "Feature",
            "id": "us20002926",
            "properties": {
                "mag": 7.8,
                "magType": "mww",
                "place": "34 km E of Lamjung, Nepal",
                "time": 1429937486000,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us20002926",
            },
            "geometry": {"type": "Point", "coordinates": [84.7314, 28.2305, 8.22]},
        },
    ],
    "metadata": {},
}


class TestFetchUSGSEvents:
    def test_successful_fetch_classifies_events(self, tmp_path):
        mock_response = MagicMock()
        mock_response.json.return_value = _VALID_GEOJSON
        mock_response.raise_for_status = MagicMock()

        with patch("ingestion.usgs_ingester.requests.get", return_value=mock_response):
            events = fetch_usgs_events(cache_path=tmp_path / "cache.json")

        assert len(events) == 2
        india_events = [e for e in events if e.geographic_scope == GeographicScope.india]
        regional_events = [e for e in events if e.geographic_scope == GeographicScope.regional]
        assert len(india_events) == 1
        assert len(regional_events) == 1
        assert india_events[0].event_id == "usp0009hkv"
        assert regional_events[0].event_id == "us20002926"

    def test_fetch_saves_cache(self, tmp_path):
        cache_path = tmp_path / "cache.json"
        mock_response = MagicMock()
        mock_response.json.return_value = _VALID_GEOJSON
        mock_response.raise_for_status = MagicMock()

        with patch("ingestion.usgs_ingester.requests.get", return_value=mock_response):
            fetch_usgs_events(cache_path=cache_path)

        assert cache_path.exists()

    def test_timeout_falls_back_to_cache(self, tmp_path, usgs_cache_path):
        import shutil
        cache_path = tmp_path / "cache.json"
        shutil.copy(usgs_cache_path, cache_path)

        import requests as req
        with patch("ingestion.usgs_ingester.requests.get",
                   side_effect=req.Timeout("timed out")):
            events = fetch_usgs_events(cache_path=cache_path)

        assert len(events) == 2  # from cache

    def test_no_cache_no_network_raises(self, tmp_path):
        import requests as req
        cache_path = tmp_path / "empty_cache.json"
        with patch("ingestion.usgs_ingester.requests.get",
                   side_effect=req.ConnectionError("no network")):
            with pytest.raises(DataSourceUnavailableError):
                fetch_usgs_events(cache_path=cache_path)

    def test_offline_mode_uses_cache(self, tmp_path, usgs_cache_path):
        import shutil
        cache_path = tmp_path / "cache.json"
        shutil.copy(usgs_cache_path, cache_path)

        events = fetch_usgs_events(offline=True, cache_path=cache_path)
        assert len(events) == 2

    def test_offline_mode_no_cache_raises(self, tmp_path):
        with pytest.raises(DataSourceUnavailableError, match="Offline mode"):
            fetch_usgs_events(offline=True, cache_path=tmp_path / "missing.json")

    def test_malformed_response_falls_back_to_cache(self, tmp_path, usgs_cache_path):
        import shutil
        cache_path = tmp_path / "cache.json"
        shutil.copy(usgs_cache_path, cache_path)

        mock_response = MagicMock()
        mock_response.json.return_value = {"type": "InvalidGeoJSON", "features": "bad"}
        mock_response.raise_for_status = MagicMock()

        with patch("ingestion.usgs_ingester.requests.get", return_value=mock_response):
            events = fetch_usgs_events(cache_path=cache_path)

        # Should have fallen back to cache
        assert len(events) >= 1

    def test_event_ids_are_preserved_verbatim(self, tmp_path):
        mock_response = MagicMock()
        mock_response.json.return_value = _VALID_GEOJSON
        mock_response.raise_for_status = MagicMock()

        with patch("ingestion.usgs_ingester.requests.get", return_value=mock_response):
            events = fetch_usgs_events(cache_path=tmp_path / "cache.json")

        ids = {e.event_id for e in events}
        assert "usp0009hkv" in ids
        assert "us20002926" in ids


# ---------------------------------------------------------------------------
# select_events_for_demo
# ---------------------------------------------------------------------------

class TestSelectEventsForDemo:
    def test_india_events_prioritised(self, chamoli_event, nepal_event):
        events = [nepal_event, chamoli_event]  # nepal first in list
        selected = select_events_for_demo(events, n=1)
        assert selected[0].event_id == chamoli_event.event_id  # India tier first

    def test_selects_up_to_n(self, chamoli_event, nepal_event):
        events = [chamoli_event, nepal_event]
        selected = select_events_for_demo(events, n=1)
        assert len(selected) == 1

    def test_falls_back_to_regional_when_no_india(self, nepal_event):
        selected = select_events_for_demo([nepal_event], n=2)
        assert len(selected) == 1
        assert selected[0].geographic_scope == GeographicScope.regional
