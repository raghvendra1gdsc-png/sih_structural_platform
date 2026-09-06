"""
ml_pipeline/dedup/candidate_filter.py — Spatial + Temporal Candidate Generation

Filters report pairs before expensive multi-modal text and image similarity computations.
Uses Haversine distance, temporal windowing, and earthquake event association to prune
the search space from O(N²) down to a small, relevant candidate set.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ml_pipeline.dedup.config import DEFAULT_DEDUP_CONFIG, DedupConfig

logger = logging.getLogger(__name__)

# Mean Earth radius in kilometers (IUGG recommendation)
EARTH_RADIUS_KM = 6371.0088


def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Calculate the great-circle distance between two geographic coordinates
    using the Haversine formula.

    All input angles in decimal degrees. Coordinate precision is preserved as-is.
    Returns:
        Distance in kilometers (>= 0.0).
    """
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    # Numerical guard against precision errors in asin sqrt
    c = 2.0 * math.atan2(math.sqrt(min(1.0, max(0.0, a))), math.sqrt(max(0.0, 1.0 - a)))
    return round(EARTH_RADIUS_KM * c, 4)


def temporal_difference_minutes(t1: datetime, t2: datetime) -> float:
    """
    Calculate the absolute time difference in minutes between two timestamps.
    Normalizes timezone-naive timestamps to UTC to avoid timezone mismatches.
    """
    if t1.tzinfo is None:
        t1 = t1.replace(tzinfo=timezone.utc)
    if t2.tzinfo is None:
        t2 = t2.replace(tzinfo=timezone.utc)

    diff_seconds = abs((t1 - t2).total_seconds())
    return round(diff_seconds / 60.0, 2)


@dataclass
class CandidatePair:
    """
    A pair of reports that passed spatial and temporal filtering and
    warrant multi-modal similarity comparison.
    """

    report_a: Any
    report_b: Any
    spatial_distance_km: float
    temporal_distance_minutes: float
    same_event: bool

    @property
    def id_a(self) -> Any:
        if isinstance(self.report_a, dict):
            return self.report_a.get("report_id", self.report_a.get("id"))
        return getattr(self.report_a, "report_id", getattr(self.report_a, "id", None))

    @property
    def id_b(self) -> Any:
        if isinstance(self.report_b, dict):
            return self.report_b.get("report_id", self.report_b.get("id"))
        return getattr(self.report_b, "report_id", getattr(self.report_b, "id", None))


def _extract_report_attrs(report: Any) -> tuple[float, float, datetime, str | None]:
    """Helper to extract lat, lon, submitted_at, and earthquake_event_id."""
    if isinstance(report, dict):
        lat = float(report["latitude"])
        lon = float(report["longitude"])
        sub = report["submitted_at"]
        if isinstance(sub, str):
            sub = datetime.fromisoformat(sub.replace("Z", "+00:00"))
        event_id = report.get("earthquake_event_id")
    else:
        lat = float(report.latitude)
        lon = float(report.longitude)
        sub = report.submitted_at
        if isinstance(sub, str):
            sub = datetime.fromisoformat(sub.replace("Z", "+00:00"))
        event_id = getattr(report, "earthquake_event_id", None)

    return lat, lon, sub, event_id


def generate_candidate_pairs(
    reports: list[Any],
    config: DedupConfig = DEFAULT_DEDUP_CONFIG,
) -> list[CandidatePair]:
    """
    Generate candidate duplicate pairs from a list of reports.

    Candidate selection rules:
    1. A report is never compared to itself.
    2. Candidate pairs must have:
       - Spatial distance <= config.SPATIAL_DISTANCE_THRESHOLD_KM
       - Temporal difference <= config.TEMPORAL_WINDOW_MINUTES
    3. If both reports specify an earthquake_event_id and they differ,
       they are not duplicates of the same event incident (pruned).

    Returns:
        List of CandidatePair instances that qualify for detailed similarity scoring.
    """
    n = len(reports)
    if n < 2:
        return []

    # Pre-extract attributes to avoid repeated attribute lookups
    extracted = [_extract_report_attrs(r) for r in reports]

    candidates: list[CandidatePair] = []

    for i in range(n):
        lat_a, lon_a, sub_a, event_a = extracted[i]
        report_a = reports[i]

        for j in range(i + 1, n):
            lat_b, lon_b, sub_b, event_b = extracted[j]
            report_b = reports[j]

            # Rule 3: Conflicting earthquake events are immediately excluded
            if event_a and event_b and event_a != event_b:
                continue

            # Check temporal window first (fast scalar arithmetic)
            dt_min = temporal_difference_minutes(sub_a, sub_b)
            if dt_min > config.TEMPORAL_WINDOW_MINUTES:
                continue

            # Bounding box pre-filter before Haversine (1 deg lat ~ 111 km)
            max_deg = (config.SPATIAL_DISTANCE_THRESHOLD_KM / 111.0) * 1.5
            if abs(lat_a - lat_b) > max_deg or abs(lon_a - lon_b) > max_deg:
                continue

            # Exact Haversine distance
            dist_km = haversine_distance_km(lat_a, lon_a, lat_b, lon_b)
            if dist_km > config.SPATIAL_DISTANCE_THRESHOLD_KM:
                continue

            same_event = bool(event_a and event_b and event_a == event_b)

            candidates.append(
                CandidatePair(
                    report_a=report_a,
                    report_b=report_b,
                    spatial_distance_km=dist_km,
                    temporal_distance_minutes=dt_min,
                    same_event=same_event,
                )
            )

    logger.info(
        "Candidate generation: %d reports evaluated -> %d candidate pairs generated.",
        n,
        len(candidates),
    )
    return candidates
