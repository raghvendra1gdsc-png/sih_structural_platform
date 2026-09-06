"""
tests/test_db_models.py
========================
Tests for the SQLAlchemy ORM models (Phase 1).
These tests do NOT require a live database connection.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from backend.db.models import Base, EarthquakeEventORM, ReportORM


class TestModelImports:
    def test_base_importable(self):
        assert Base is not None

    def test_earthquake_event_orm_importable(self):
        assert EarthquakeEventORM is not None

    def test_report_orm_importable(self):
        assert ReportORM is not None

    def test_earthquake_event_table_name(self):
        assert EarthquakeEventORM.__tablename__ == "earthquake_events"

    def test_report_table_name(self):
        assert ReportORM.__tablename__ == "reports"


class TestEarthquakeEventORM:
    def test_columns_exist(self):
        cols = {c.name for c in EarthquakeEventORM.__table__.columns}
        required = {
            "id", "event_id", "source", "magnitude", "magnitude_type",
            "latitude", "longitude", "depth_km", "geometry", "place",
            "event_time", "url", "geographic_scope", "created_at",
        }
        assert required.issubset(cols), f"Missing columns: {required - cols}"

    def test_event_id_is_unique(self):
        event_id_col = EarthquakeEventORM.__table__.columns["event_id"]
        assert event_id_col.unique

    def test_geometry_column_present(self):
        cols = EarthquakeEventORM.__table__.columns
        assert "geometry" in [c.name for c in cols]

    def test_instantiate_without_db(self):
        """ORM objects can be created without a DB session."""
        obj = EarthquakeEventORM(
            id=uuid.uuid4(),
            event_id="usp0009hkv",
            source="usgs",
            magnitude=6.6,
            magnitude_type="mw",
            latitude=30.408,
            longitude=79.416,
            depth_km=15.0,
            place="Chamoli, Uttarakhand, India",
            event_time=datetime(1999, 3, 29, tzinfo=timezone.utc),
            url="https://earthquake.usgs.gov/earthquakes/eventpage/usp0009hkv",
            geographic_scope="india",
        )
        assert obj.event_id == "usp0009hkv"
        assert obj.geographic_scope == "india"


class TestReportORM:
    def test_columns_exist(self):
        cols = {c.name for c in ReportORM.__table__.columns}
        required = {
            "id", "report_id", "source", "submitted_at", "latitude", "longitude",
            "geometry", "location_text", "text", "earthquake_event_id",
            "damage_type", "severity", "verification_status", "trust_score",
            "duplicate_of", "is_synthetic", "created_at",
        }
        assert required.issubset(cols), f"Missing columns: {required - cols}"

    def test_report_id_is_unique(self):
        report_id_col = ReportORM.__table__.columns["report_id"]
        assert report_id_col.unique

    def test_is_synthetic_column_not_nullable(self):
        col = ReportORM.__table__.columns["is_synthetic"]
        assert not col.nullable

    def test_trust_score_is_nullable(self):
        col = ReportORM.__table__.columns["trust_score"]
        assert col.nullable

    def test_instantiate_without_db(self):
        rid = uuid.uuid4()
        obj = ReportORM(
            id=uuid.uuid4(),
            report_id=rid,
            source="synthetic",
            submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
            latitude=30.41,
            longitude=79.42,
            damage_type="unknown",
            severity="unknown",
            verification_status="pending",
            is_synthetic=True,
        )
        assert obj.report_id == rid
        assert obj.is_synthetic is True

    def test_fk_to_earthquake_events(self):
        """FK from reports.earthquake_event_id → earthquake_events.event_id."""
        fks = {fk.target_fullname for fk in ReportORM.__table__.foreign_keys}
        assert "earthquake_events.event_id" in fks

    def test_metadata_tables(self):
        """Both tables registered in Base.metadata."""
        table_names = set(Base.metadata.tables.keys())
        assert "earthquake_events" in table_names
        assert "reports" in table_names
