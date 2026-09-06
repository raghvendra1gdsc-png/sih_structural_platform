"""
ingestion/normaliser.py
========================
Normalisation pipeline: RawReport → NormalizedReport.

Rules
-----
- Timestamps are always converted to UTC (naive datetimes are assumed UTC).
- Coordinate precision is preserved as-is (no rounding).
- Text is stripped of leading/trailing whitespace; empty strings become None.
- location_text is stripped similarly.
- verification_status is always initialised to ``pending``.
- trust_score is always initialised to ``None`` — the trust-scoring module
  (Phase 4) will populate it.  Never hardcode or randomly assign this value.
- duplicate_of is always initialised to ``None`` (dedup is Phase 2).
- is_synthetic, source, earthquake_event_id are propagated verbatim.
- damage_type and severity provided by the synthetic generator are preserved;
  if absent they default to ``unknown``.
- ML-based damage classification is NOT performed here (Phase 3).

Raises
------
NormalisationError
    If the RawReport is structurally invalid and cannot be normalised.
"""

from __future__ import annotations

import logging
import unicodedata
from datetime import datetime, timezone
from typing import Optional

from ingestion.schemas import (
    DamageSeverity,
    DamageType,
    NormalizedReport,
    RawReport,
    ReportSource,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class NormalisationError(ValueError):
    """
    Raised when a RawReport cannot be normalised.

    Callers should log these and skip the offending record rather than crashing
    the entire pipeline.
    """


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _clean_text(text: Optional[str]) -> Optional[str]:
    """
    Normalise a free-text field.

    Steps:
      1. Unicode NFC normalisation (composing form).
      2. Strip leading/trailing whitespace.
      3. Collapse internal runs of whitespace to a single space.
      4. Return None if the result is empty.
    """
    if text is None:
        return None
    # NFC normalisation
    normalised = unicodedata.normalize("NFC", text)
    # Strip and collapse whitespace
    cleaned = " ".join(normalised.split())
    return cleaned if cleaned else None


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------


def _to_utc(dt: datetime) -> datetime:
    """
    Return a timezone-aware datetime in UTC.

    If the input is naive (tzinfo=None) it is assumed to already be UTC,
    per AGENTS.md §7.5: "All timestamps must be stored in UTC."
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Coordinate validation
# ---------------------------------------------------------------------------


def _validate_coords(lat: Optional[float], lon: Optional[float]) -> tuple[float, float]:
    """
    Validate and return (latitude, longitude).

    Raises NormalisationError if coordinates are missing or out of range.
    """
    if lat is None or lon is None:
        raise NormalisationError("Latitude and longitude are required for normalisation.")
    if not (-90.0 <= lat <= 90.0):
        raise NormalisationError(f"Latitude {lat} is out of range [-90, 90].")
    if not (-180.0 <= lon <= 180.0):
        raise NormalisationError(f"Longitude {lon} is out of range [-180, 180].")
    return lat, lon


# ---------------------------------------------------------------------------
# Core normalisation
# ---------------------------------------------------------------------------


def normalise(
    raw: RawReport,
    *,
    known_event_ids: Optional[set[str]] = None,
) -> NormalizedReport:
    """
    Convert a single ``RawReport`` into a ``NormalizedReport``.

    Parameters
    ----------
    raw : RawReport
        The raw report to normalise.
    known_event_ids : set[str] | None
        Optional set of valid USGS event IDs from the ingested event cache.
        If provided, the normaliser will warn when ``earthquake_event_id`` is
        not found in the set (but will NOT reject the record — validation is
        the caller's responsibility).

    Returns
    -------
    NormalizedReport
        A fully normalised record ready for PostGIS storage.

    Raises
    ------
    NormalisationError
        If the report cannot be normalised (e.g. no coordinates, bad timestamp).
    """
    # 1. Timestamp → UTC
    try:
        timestamp_utc = _to_utc(raw.submitted_at)
    except Exception as exc:
        raise NormalisationError(
            f"Cannot convert submitted_at to UTC for report {raw.report_id}: {exc}"
        ) from exc

    # 2. Coordinates — required for PostGIS storage
    try:
        lat, lon = _validate_coords(raw.latitude, raw.longitude)
    except NormalisationError:
        # If coordinates are missing but location_text is present, we cannot
        # insert a PostGIS point.  Log the warning and re-raise.
        raise NormalisationError(
            f"Report {raw.report_id} has no valid coordinates. "
            "Cannot create PostGIS geometry without lat/lon."
        )

    # 3. Text cleaning
    cleaned_text = _clean_text(raw.text)
    cleaned_location = _clean_text(raw.location_text)

    # 4. image_reference — preserve as-is (CLIP validation in Phase 3)
    image_ref = raw.image_reference.strip() if raw.image_reference else None
    if image_ref == "":
        image_ref = None

    # 5. Validate earthquake_event_id against known events (advisory only)
    eq_event_id = raw.earthquake_event_id
    if known_event_ids is not None and eq_event_id is not None:
        if eq_event_id not in known_event_ids:
            logger.warning(
                "Report %s references earthquake_event_id=%r which is not in the "
                "known event cache. Record normalised but flagged for review.",
                raw.report_id,
                eq_event_id,
            )

    # 6. Preserve damage info supplied by synthetic generator
    #    (Phase 3 will overwrite with CLIP results; we do NOT touch these now)
    #    Synthetic generator stores damage_type in text via _pick_damage_type;
    #    for Phase 1 we default to unknown unless the caller has pre-populated.
    #    The RawReport schema does not carry damage_type/severity — they live
    #    on NormalizedReport.  So we always start with unknown here.
    damage_type = DamageType.unknown
    severity = DamageSeverity.unknown

    # 7. Construct the NormalizedReport
    normalised = NormalizedReport(
        report_id=raw.report_id,          # preserve original UUID
        source=raw.source,
        timestamp=timestamp_utc,
        latitude=lat,
        longitude=lon,
        location_text=cleaned_location,
        text=cleaned_text,
        image_reference=image_ref,
        earthquake_event_id=eq_event_id,
        damage_type=damage_type,
        severity=severity,
        verification_status=VerificationStatus.pending,
        trust_score=None,                  # populated by Phase 4 trust-scoring
        duplicate_of=None,                 # populated by Phase 2 dedup
        is_synthetic=raw.is_synthetic,
    )

    return normalised


def normalise_batch(
    reports: list[RawReport],
    *,
    known_event_ids: Optional[set[str]] = None,
) -> tuple[list[NormalizedReport], list[tuple[RawReport, Exception]]]:
    """
    Normalise a list of ``RawReport`` objects.

    Parameters
    ----------
    reports : list[RawReport]
    known_event_ids : set[str] | None

    Returns
    -------
    (successes, failures)
        successes: list of successfully normalised NormalizedReport objects.
        failures:  list of (raw_report, exception) tuples for failed records.
    """
    successes: list[NormalizedReport] = []
    failures: list[tuple[RawReport, Exception]] = []

    for raw in reports:
        try:
            normalised = normalise(raw, known_event_ids=known_event_ids)
            successes.append(normalised)
        except (NormalisationError, Exception) as exc:
            logger.warning(
                "Failed to normalise report %s: %s",
                raw.report_id,
                exc,
            )
            failures.append((raw, exc))

    logger.info(
        "Normalisation complete: %d succeeded, %d failed.",
        len(successes),
        len(failures),
    )
    return successes, failures
