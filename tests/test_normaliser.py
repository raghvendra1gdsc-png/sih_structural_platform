"""
tests/test_normaliser.py
=========================
Tests for the normalisation pipeline (Phase 1).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from ingestion.normaliser import NormalisationError, normalise, normalise_batch
from ingestion.schemas import (
    DamageSeverity,
    DamageType,
    NormalizedReport,
    RawReport,
    ReportSource,
    VerificationStatus,
)


# ---------------------------------------------------------------------------
# Happy-path normalisation
# ---------------------------------------------------------------------------

class TestNormalise:
    def test_valid_report_normalises(self, minimal_raw_report):
        result = normalise(minimal_raw_report)
        assert isinstance(result, NormalizedReport)

    def test_report_id_preserved(self, minimal_raw_report):
        result = normalise(minimal_raw_report)
        assert result.report_id == minimal_raw_report.report_id

    def test_source_preserved(self, minimal_raw_report):
        result = normalise(minimal_raw_report)
        assert result.source == minimal_raw_report.source

    def test_is_synthetic_preserved(self, minimal_raw_report):
        result = normalise(minimal_raw_report)
        assert result.is_synthetic is True

    def test_earthquake_event_id_preserved(self, minimal_raw_report):
        result = normalise(minimal_raw_report)
        assert result.earthquake_event_id == minimal_raw_report.earthquake_event_id

    def test_coordinates_preserved_exactly(self):
        """Coordinate precision must NOT be rounded."""
        r = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
            latitude=28.123456789,
            longitude=77.987654321,
            is_synthetic=True,
        )
        result = normalise(r)
        assert result.latitude == 28.123456789
        assert result.longitude == 77.987654321

    def test_naive_timestamp_assumed_utc(self):
        """Naive datetimes should be treated as UTC."""
        r = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 6, 15, 10, 30, 0),  # naive
            latitude=20.0,
            longitude=78.0,
            is_synthetic=True,
        )
        result = normalise(r)
        assert result.timestamp.tzinfo is not None
        assert result.timestamp.utcoffset() == timedelta(0)

    def test_aware_timestamp_converted_to_utc(self):
        """Non-UTC aware datetimes should be converted."""
        from datetime import timezone
        ist = timezone(timedelta(hours=5, minutes=30))
        r = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 6, 15, 16, 0, 0, tzinfo=ist),  # IST
            latitude=20.0,
            longitude=78.0,
            is_synthetic=True,
        )
        result = normalise(r)
        # 16:00 IST = 10:30 UTC
        assert result.timestamp.hour == 10
        assert result.timestamp.minute == 30
        assert result.timestamp.tzinfo == timezone.utc

    def test_verification_status_defaults_pending(self, minimal_raw_report):
        result = normalise(minimal_raw_report)
        assert result.verification_status == VerificationStatus.pending

    def test_trust_score_is_none(self, minimal_raw_report):
        """Trust score must never be set here."""
        result = normalise(minimal_raw_report)
        assert result.trust_score is None

    def test_duplicate_of_is_none(self, minimal_raw_report):
        """Deduplication field must never be set here."""
        result = normalise(minimal_raw_report)
        assert result.duplicate_of is None

    def test_damage_defaults_unknown(self, minimal_raw_report):
        """No ML in Phase 1 — damage_type and severity default to unknown."""
        result = normalise(minimal_raw_report)
        assert result.damage_type == DamageType.unknown
        assert result.severity == DamageSeverity.unknown

    def test_text_stripped(self):
        r = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
            latitude=20.0,
            longitude=78.0,
            text="  Building cracked.   ",
            is_synthetic=True,
        )
        result = normalise(r)
        assert result.text == "Building cracked."

    def test_text_with_extra_internal_spaces_collapsed(self):
        r = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
            latitude=20.0,
            longitude=78.0,
            text="Building  cracked   badly.",
            is_synthetic=True,
        )
        result = normalise(r)
        assert result.text == "Building cracked badly."

    def test_empty_text_becomes_none(self):
        r = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
            latitude=20.0,
            longitude=78.0,
            text="   ",
            is_synthetic=True,
        )
        result = normalise(r)
        assert result.text is None

    def test_location_text_cleaned(self):
        r = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
            latitude=20.0,
            longitude=78.0,
            location_text="  Chamoli   district  ",
            is_synthetic=True,
        )
        result = normalise(r)
        assert result.location_text == "Chamoli district"

    def test_known_event_ids_warns_on_unknown(self, minimal_raw_report, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            normalise(minimal_raw_report, known_event_ids={"other_event_id"})
        assert "not in the known event cache" in caplog.text

    def test_known_event_ids_no_warning_when_valid(self, minimal_raw_report, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            normalise(
                minimal_raw_report,
                known_event_ids={minimal_raw_report.earthquake_event_id},
            )
        assert "not in the known event cache" not in caplog.text


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestNormalisationErrors:
    def test_missing_coords_raises(self):
        """Reports with only location_text cannot form PostGIS geometry."""
        r = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
            location_text="Somewhere",
            is_synthetic=True,
        )
        with pytest.raises(NormalisationError, match="no valid coordinates"):
            normalise(r)


# ---------------------------------------------------------------------------
# Batch normalisation
# ---------------------------------------------------------------------------

class TestNormaliseBatch:
    def test_batch_all_succeed(self, minimal_raw_report):
        r2 = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 2, 1, tzinfo=timezone.utc),
            latitude=28.6,
            longitude=77.3,
            is_synthetic=True,
        )
        successes, failures = normalise_batch([minimal_raw_report, r2])
        assert len(successes) == 2
        assert len(failures) == 0

    def test_batch_partial_failure(self, minimal_raw_report):
        """A report with no coords fails; others succeed."""
        bad = RawReport(
            source=ReportSource.synthetic,
            submitted_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
            location_text="Only text, no coords",
            is_synthetic=True,
        )
        successes, failures = normalise_batch([minimal_raw_report, bad])
        assert len(successes) == 1
        assert len(failures) == 1
        assert failures[0][0] == bad

    def test_batch_empty_input(self):
        successes, failures = normalise_batch([])
        assert successes == []
        assert failures == []
