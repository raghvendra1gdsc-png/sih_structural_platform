"""
tests/test_schemas.py
======================
Tests for Pydantic schemas (Phase 0/1).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ingestion.schemas import (
    DamageSeverity,
    DamageType,
    EarthquakeEvent,
    GeographicScope,
    MagnitudeType,
    NormalizedReport,
    RawReport,
    ReportSource,
    USGSFeature,
    USGSFeatureCollection,
    USGSFeatureGeometry,
    USGSFeatureProperties,
    VerificationStatus,
)


# ---------------------------------------------------------------------------
# EarthquakeEvent
# ---------------------------------------------------------------------------

class TestEarthquakeEvent:
    def test_valid_event(self):
        e = EarthquakeEvent(
            event_id="usp0009hkv",
            magnitude=6.6,
            magnitude_type=MagnitudeType.mw,
            latitude=30.408,
            longitude=79.416,
            depth_km=15.0,
            place="Chamoli, Uttarakhand, India",
            event_time=datetime(1999, 3, 29, 0, 35, tzinfo=timezone.utc),
            url="https://earthquake.usgs.gov/earthquakes/eventpage/usp0009hkv",
        )
        assert e.event_id == "usp0009hkv"
        assert e.geographic_scope == GeographicScope.other  # default

    def test_geographic_scope_default_is_other(self):
        e = EarthquakeEvent(
            event_id="test001",
            magnitude=5.5,
            latitude=20.0,
            longitude=80.0,
            depth_km=10.0,
            place="Some place",
            event_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
            url="https://example.com",
        )
        assert e.geographic_scope == GeographicScope.other

    def test_epoch_ms_conversion(self):
        """USGS returns time as epoch milliseconds."""
        e = EarthquakeEvent(
            event_id="test002",
            magnitude=5.0,
            latitude=25.0,
            longitude=75.0,
            depth_km=10.0,
            place="Rajasthan, India",
            event_time=1617235200000,   # 2021-04-01 00:00:00 UTC in ms
            url="https://earthquake.usgs.gov/earthquakes/eventpage/test002",
        )
        assert e.event_time.year == 2021
        assert e.event_time.month == 4

    def test_unknown_magnitude_type_coerced(self):
        e = EarthquakeEvent(
            event_id="test003",
            magnitude=6.0,
            magnitude_type="xyz_unknown_type",
            latitude=28.0,
            longitude=77.0,
            depth_km=5.0,
            place="Delhi, India",
            event_time=datetime(2020, 6, 1, tzinfo=timezone.utc),
            url="https://earthquake.usgs.gov",
        )
        assert e.magnitude_type == MagnitudeType.unknown

    def test_invalid_magnitude_rejected(self):
        with pytest.raises(ValidationError):
            EarthquakeEvent(
                event_id="bad",
                magnitude=11.0,      # > 10.0 limit
                latitude=20.0,
                longitude=80.0,
                depth_km=10.0,
                place="Somewhere",
                event_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
                url="https://example.com",
            )

    def test_invalid_latitude_rejected(self):
        with pytest.raises(ValidationError):
            EarthquakeEvent(
                event_id="bad2",
                magnitude=5.0,
                latitude=95.0,      # > 90
                longitude=80.0,
                depth_km=10.0,
                place="Somewhere",
                event_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
                url="https://example.com",
            )

    def test_geographic_scope_india_preserved(self):
        e = EarthquakeEvent(
            event_id="ind001",
            magnitude=6.0,
            latitude=25.0,
            longitude=80.0,
            depth_km=10.0,
            place="Uttar Pradesh, India",
            event_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
            url="https://example.com",
            geographic_scope=GeographicScope.india,
        )
        assert e.geographic_scope == GeographicScope.india


# ---------------------------------------------------------------------------
# RawReport
# ---------------------------------------------------------------------------

class TestRawReport:
    def test_valid_synthetic_report(self):
        r = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            latitude=28.5,
            longitude=77.2,
            location_text="Delhi, India",
            text="Cracks visible in walls.",
            is_synthetic=True,
            earthquake_event_id="usp0009hkv",
        )
        assert r.is_synthetic is True
        assert r.source == ReportSource.synthetic

    def test_synthetic_must_use_synthetic_source(self):
        """is_synthetic=True with source=usgs should fail."""
        with pytest.raises(ValidationError, match="source=ReportSource.synthetic"):
            RawReport(
                source=ReportSource.usgs,
                submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
                latitude=28.5,
                longitude=77.2,
                is_synthetic=True,
                location_text="Somewhere",
            )

    def test_no_location_raises(self):
        """Report with neither coords nor location_text must fail."""
        with pytest.raises(ValidationError, match="must have either"):
            RawReport(
                source=ReportSource.synthetic,
                submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
                is_synthetic=True,
            )

    def test_location_text_only_accepted(self):
        """A report with only location_text (no coords) is valid at this stage."""
        r = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
            location_text="Somewhere in Uttarakhand",
            is_synthetic=True,
        )
        assert r.latitude is None
        assert r.longitude is None

    def test_invalid_longitude_rejected(self):
        with pytest.raises(ValidationError):
            RawReport(
                source=ReportSource.synthetic,
                submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
                latitude=28.5,
                longitude=200.0,    # > 180
                is_synthetic=True,
            )

    def test_report_id_auto_generated(self):
        r = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
            latitude=28.5,
            longitude=77.2,
            is_synthetic=True,
        )
        assert isinstance(r.report_id, uuid.UUID)

    def test_not_synthetic_report(self):
        """A non-synthetic report with source=citizen_api is valid."""
        r = RawReport(
            source=ReportSource.citizen_api,
            submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
            latitude=19.1,
            longitude=72.8,
            text="Building collapsed near us.",
            is_synthetic=False,
        )
        assert r.is_synthetic is False


# ---------------------------------------------------------------------------
# NormalizedReport
# ---------------------------------------------------------------------------

class TestNormalizedReport:
    def test_valid_normalized(self):
        n = NormalizedReport(
            source=ReportSource.synthetic,
            timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
            latitude=28.5,
            longitude=77.2,
            is_synthetic=True,
        )
        assert n.verification_status == VerificationStatus.pending
        assert n.trust_score is None
        assert n.duplicate_of is None
        assert n.damage_type == DamageType.unknown
        assert n.severity == DamageSeverity.unknown

    def test_synthetic_flag_must_match_source(self):
        with pytest.raises(ValidationError, match="source is not 'synthetic'"):
            NormalizedReport(
                source=ReportSource.citizen_api,
                timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
                latitude=28.5,
                longitude=77.2,
                is_synthetic=True,      # contradicts source
            )

    def test_trust_score_validation(self):
        with pytest.raises(ValidationError):
            NormalizedReport(
                source=ReportSource.synthetic,
                timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
                latitude=28.5,
                longitude=77.2,
                is_synthetic=True,
                trust_score=1.5,        # > 1.0 limit
            )

    def test_all_enums_valid(self):
        n = NormalizedReport(
            source=ReportSource.synthetic,
            timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
            latitude=28.5,
            longitude=77.2,
            is_synthetic=True,
            damage_type=DamageType.partial_collapse,
            severity=DamageSeverity.severe,
            verification_status=VerificationStatus.verified,
        )
        assert n.damage_type == DamageType.partial_collapse
        assert n.severity == DamageSeverity.severe


# ---------------------------------------------------------------------------
# USGSFeature / USGSFeatureCollection
# ---------------------------------------------------------------------------

class TestUSGSParsing:
    def test_parse_feature_collection(self):
        raw = {
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
                    "geometry": {
                        "type": "Point",
                        "coordinates": [79.416, 30.408, 15.0],
                    },
                }
            ],
            "metadata": {},
        }
        collection = USGSFeatureCollection.model_validate(raw)
        assert len(collection.features) == 1
        feature = collection.features[0]
        assert feature.id == "usp0009hkv"
        event = feature.to_earthquake_event(geographic_scope=GeographicScope.india)
        assert event.latitude == 30.408
        assert event.longitude == 79.416
        assert event.geographic_scope == GeographicScope.india

    def test_missing_coordinates_rejected(self):
        with pytest.raises(ValidationError):
            USGSFeatureGeometry(type="Point", coordinates=[79.0, 30.0])  # only 2 elements

    def test_missing_mag_rejected(self):
        with pytest.raises(ValidationError):
            USGSFeatureProperties(place="Somewhere", time=1000, url="https://example.com")

    def test_extra_properties_allowed(self):
        """USGS adds many extra fields; extra='allow' must accept them."""
        props = USGSFeatureProperties(
            mag=5.5,
            magType="mb",
            place="Somewhere",
            time=1000000,
            url="https://example.com",
            felt=100,           # extra USGS field
            alert="green",      # extra USGS field
        )
        assert props.mag == 5.5
