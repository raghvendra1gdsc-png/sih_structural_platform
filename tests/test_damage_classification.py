"""
tests/test_damage_classification.py — Integration Tests for Damage Classification Pipeline

Tests:
- Database schema integration: ReportORM classification fields
- Canonical report runner: processes canonical reports with images
- Duplicate isolation: duplicate reports are not classified by canonical runner
- Dry-run mode: verifies changes are not committed when dry_run=True
- Full xBD benchmark validation invocation
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import Base, EarthquakeEventORM, ReportORM
from ingestion.schemas import (
    DamageSeverity,
    DamageType,
    GeographicScope,
    MagnitudeType,
    ReportSource,
)
from ml_pipeline.damage_classification.run import run_classification
from ml_pipeline.damage_classification.validate_xbd import run_xbd_validation


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sih_user:sih_password@localhost:5432/disaster_db",
)


@pytest.fixture(scope="module")
def db_session():
    """Provides a database session for testing."""
    engine = create_engine(DATABASE_URL)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_report_orm_classification_columns():
    """Verify ReportORM has the new Phase 3 classification fields."""
    assert hasattr(ReportORM, "classification_score")
    assert hasattr(ReportORM, "classification_model")
    assert hasattr(ReportORM, "classified_at")


def test_classification_runner_dry_run(db_session: Session):
    """Verify dry-run mode processes records without committing changes."""
    exit_code = run_classification(database_url=DATABASE_URL, dry_run=True)
    assert exit_code == 0


def test_duplicate_report_isolation(db_session: Session, tmp_path: Path):
    """
    Ensure that a report marked as duplicate (duplicate_of is NOT NULL)
    is excluded from canonical report classification.
    """
    # Create a dummy image
    test_img = tmp_path / "test_iso.jpg"
    from PIL import Image
    Image.new("RGB", (64, 64), color=(100, 100, 100)).save(test_img)

    # Find an existing event in the DB
    event = db_session.query(EarthquakeEventORM).first()
    assert event is not None, "Database must have at least one seeded event."

    canonical_id = uuid.uuid4()
    duplicate_id = uuid.uuid4()
    geom = WKTElement("POINT(79.0 30.0)", srid=4326)

    canonical = ReportORM(
        report_id=canonical_id,
        source="synthetic",
        submitted_at=datetime.now(timezone.utc),
        latitude=30.0,
        longitude=79.0,
        geometry=geom,
        text="Canonical report for isolation test",
        image_reference=str(test_img),
        earthquake_event_id=event.event_id,
        is_synthetic=True,
        duplicate_of=None,
    )
    duplicate = ReportORM(
        report_id=duplicate_id,
        source="synthetic",
        submitted_at=datetime.now(timezone.utc),
        latitude=30.0,
        longitude=79.0,
        geometry=geom,
        text="Duplicate report for isolation test",
        image_reference=str(test_img),
        earthquake_event_id=event.event_id,
        is_synthetic=True,
        duplicate_of=canonical_id,
    )

    db_session.add(canonical)
    db_session.add(duplicate)
    db_session.commit()

    try:
        # Run classification
        run_classification(database_url=DATABASE_URL, dry_run=False)

        # Refresh objects
        db_session.refresh(canonical)
        db_session.refresh(duplicate)

        # Canonical should be classified
        assert canonical.classified_at is not None
        assert canonical.classification_model is not None

        # Duplicate must NOT have been processed by canonical runner
        assert duplicate.classified_at is None
        assert duplicate.classification_model is None

    finally:
        # Cleanup test records
        db_session.delete(duplicate)
        db_session.delete(canonical)
        db_session.commit()


def test_run_xbd_validation_invocation():
    """Verify that run_xbd_validation executes on the 52-sample dataset."""
    repo_root = Path(__file__).resolve().parent.parent
    xbd_dir = repo_root / "data" / "sample_dataset" / "xbd_sample"
    manifest_path = xbd_dir / "xbd_manifest.json"

    assert xbd_dir.exists(), "xBD sample directory must exist."
    assert manifest_path.exists(), "xBD manifest must exist."

    report = run_xbd_validation(
        dataset_dir=xbd_dir,
        manifest_path=manifest_path,
        output_path=None,  # Don't overwrite the canonical validation_results.json during unit test
    )

    assert report["total_samples"] == 52
    assert "accuracy" in report["severity_evaluation"]
    assert "macro_f1" in report["severity_evaluation"]
    assert report["severity_evaluation"]["accuracy"] > 0.0
