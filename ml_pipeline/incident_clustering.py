"""
ml_pipeline/incident_clustering.py
==================================
Geospatial Spatiotemporal Clustering & Platform Impact Scoring.

Clusters multiple canonical weather reports into cohesive `WeatherIncident`s (hotspots),
computing:
- Incident Centroid (latitude, longitude)
- Bounding radius / spread
- Start and End time bounds
- Aggregated report count and verified count
- Platform-derived Weather Impact Score [0–100] (LOW, MODERATE, HIGH, SEVERE)
- Natural language incident summary
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ingestion.weather_schemas import (
    NormalizedWeatherReport,
    SeverityLevel,
    WeatherEventCategory,
    WeatherIncidentSchema,
)
from ml_pipeline.weather_dedup import haversine_distance_km

logger = logging.getLogger(__name__)


def calculate_platform_impact_score(
    report_count: int,
    verified_count: int,
    category: WeatherEventCategory,
    radius_km: float,
    reports_per_hour: float,
) -> tuple[float, SeverityLevel]:
    """
    Calculate transparent 0-100 Platform-Derived Weather Impact Score.
    Signals:
    - Volume & Velocity of reports (max 35)
    - Verification Ratio (max 20)
    - Category Inherent Severity (max 25)
    - Geospatial Spread / Density (max 20)
    """
    # 1. Volume & Velocity
    vol_score = min(35.0, (report_count * 1.5) + (reports_per_hour * 2.0))

    # 2. Verification Weight
    v_ratio = (verified_count / max(1, report_count))
    verif_score = v_ratio * 20.0

    # 3. Inherent Category Hazard
    cat_hazard = {
        WeatherEventCategory.cyclone: 25.0,
        WeatherEventCategory.flooding: 23.0,
        WeatherEventCategory.landslide: 24.0,
        WeatherEventCategory.thunderstorm: 20.0,
        WeatherEventCategory.hailstorm: 19.0,
        WeatherEventCategory.lightning: 18.0,
        WeatherEventCategory.dust_storm: 17.0,
        WeatherEventCategory.heatwave: 16.0,
        WeatherEventCategory.strong_winds: 15.0,
        WeatherEventCategory.rainfall: 14.0,
        WeatherEventCategory.cold_wave: 12.0,
        WeatherEventCategory.fog: 10.0,
        WeatherEventCategory.other: 8.0,
    }
    cat_score = cat_hazard.get(category, 10.0)

    # 4. Spread factor
    spread_score = min(20.0, (radius_km * 2.0))

    total = vol_score + verif_score + cat_score + spread_score
    impact_score = round(min(100.0, max(5.0, total)), 1)

    if impact_score <= 25.0:
        severity = SeverityLevel.low
    elif impact_score <= 50.0:
        severity = SeverityLevel.moderate
    elif impact_score <= 75.0:
        severity = SeverityLevel.high
    else:
        severity = SeverityLevel.severe

    return impact_score, severity


class IncidentClusteringEngine:
    """
    Clusters reports by city/locality, category, spatial proximity (<= 15 km),
    and temporal proximity (<= 180 mins).
    """

    def __init__(
        self,
        cluster_distance_km: float = 12.0,
        cluster_window_minutes: float = 240.0,
    ) -> None:
        self.cluster_distance_km = cluster_distance_km
        self.cluster_window_minutes = cluster_window_minutes

    def cluster_reports(
        self,
        reports: list[NormalizedWeatherReport],
    ) -> list[WeatherIncidentSchema]:
        """
        Group normalized weather reports into distinct weather incidents.
        Only clusters non-duplicate (or canonical) reports.
        """
        # Filter to canonical reports or unique reports
        active_reports = [r for r in reports if r.duplicate_of is None]
        if not active_reports:
            return []

        # Sort by city and event_time
        active_reports.sort(key=lambda r: (r.city, r.event_time))

        clusters: list[list[NormalizedWeatherReport]] = []

        for rep in active_reports:
            assigned = False
            for cluster in clusters:
                # Check if compatible with cluster anchor
                anchor = cluster[0]
                # Must match city and compatible category
                if anchor.city == rep.city:
                    cat_match = (
                        anchor.event_category == rep.event_category
                        or {anchor.event_category, rep.event_category} <= {
                            WeatherEventCategory.rainfall,
                            WeatherEventCategory.flooding,
                            WeatherEventCategory.thunderstorm,
                        }
                    )
                    if cat_match:
                        # Check spatial distance to anchor
                        dist = haversine_distance_km(anchor.latitude, anchor.longitude, rep.latitude, rep.longitude)
                        if dist <= self.cluster_distance_km:
                            # Check time delta
                            t1 = anchor.event_time.astimezone(timezone.utc)
                            t2 = rep.event_time.astimezone(timezone.utc)
                            dt_mins = abs((t1 - t2).total_seconds()) / 60.0
                            if dt_mins <= self.cluster_window_minutes:
                                cluster.append(rep)
                                assigned = True
                                break
            if not assigned:
                clusters.append([rep])

        incidents: list[WeatherIncidentSchema] = []

        for cluster in clusters:
            if not cluster:
                continue

            city = cluster[0].city
            state = cluster[0].state
            cat = cluster[0].event_category

            # Compute centroid
            avg_lat = sum(r.latitude for r in cluster) / len(cluster)
            avg_lon = sum(r.longitude for r in cluster) / len(cluster)

            # Compute max radius from centroid
            max_radius = 2.0
            for r in cluster:
                d = haversine_distance_km(avg_lat, avg_lon, r.latitude, r.longitude)
                if d > max_radius:
                    max_radius = d
            radius_km = round(min(30.0, max(2.5, max_radius + 1.0)), 1)

            # Time bounds
            times = [r.event_time.astimezone(timezone.utc) for r in cluster]
            start_time = min(times)
            end_time = max(times)

            # Report counts
            rep_count = len(cluster)
            verif_count = sum(1 for r in cluster if r.verification_status.value == "verified")

            duration_hours = max(0.5, (end_time - start_time).total_seconds() / 3600.0)
            velocity = rep_count / duration_hours

            impact_score, severity = calculate_platform_impact_score(
                report_count=rep_count,
                verified_count=verif_count,
                category=cat,
                radius_km=radius_km,
                reports_per_hour=velocity,
            )

            summary = (
                f"{cat.value.replace('_', ' ').title()} incident in {city} "
                f"encompassing {rep_count} citizen observation(s) across a {radius_km} km zone. "
                f"Platform Impact Score: {impact_score:.0f}/100 ({severity.value.upper()})."
            )

            incidents.append(
                WeatherIncidentSchema(
                    incident_id=uuid.uuid4(),
                    event_category=cat,
                    centroid_lat=round(avg_lat, 5),
                    centroid_lon=round(avg_lon, 5),
                    start_time=start_time,
                    end_time=end_time,
                    report_count=rep_count,
                    verified_count=verif_count,
                    severity=severity,
                    impact_score=impact_score,
                    confidence=0.85,
                    city=city,
                    state=state,
                    radius_km=radius_km,
                    summary=summary,
                )
            )

        # Sort by impact score descending
        incidents.sort(key=lambda x: x.impact_score, reverse=True)
        return incidents


DEFAULT_CLUSTERING_ENGINE = IncidentClusteringEngine()
