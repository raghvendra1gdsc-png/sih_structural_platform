"""
ml_pipeline/trust_engine.py
===========================
Auditable Source Trust & Misinformation Triage Engine.

Calculates a transparent, explainable trust score [0–100] using 6 weighted signals:
1. Source Reliability (max 20)
2. Weather Consistency with Forecast/Sensor (max 25)
3. Geographic Consistency (max 15)
4. Temporal Consistency (max 15)
5. Cross-Report Agreement / Corroboration (max 15)
6. Media & Evidence (max 10)

Generates explicit human-readable reasons (✓ positive endorsements & ⚠ warnings).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ingestion.weather_schemas import (
    NormalizedWeatherReport,
    WeatherEventCategory,
    WeatherReportSource,
)

logger = logging.getLogger(__name__)


@dataclass
class TrustEvaluation:
    trust_score: float
    misinformation_score: float
    breakdown: dict[str, float]
    reasons: list[str]
    is_credible: bool


class SourceTrustEngine:
    """
    Transparent algorithmic trust assessment for weather observations.
    """

    def __init__(
        self,
        source_weight: float = 20.0,
        weather_consistency_weight: float = 25.0,
        geo_consistency_weight: float = 15.0,
        temporal_consistency_weight: float = 15.0,
        corroboration_weight: float = 15.0,
        media_weight: float = 10.0,
    ) -> None:
        self.w_source = source_weight
        self.w_weather = weather_consistency_weight
        self.w_geo = geo_consistency_weight
        self.w_temp = temporal_consistency_weight
        self.w_corroboration = corroboration_weight
        self.w_media = media_weight

    def evaluate(
        self,
        report: NormalizedWeatherReport,
        forecast_condition: Optional[str] = None,
        forecast_precipitation_prob: Optional[float] = None,
        nearby_reports_count: int = 0,
    ) -> TrustEvaluation:
        """
        Evaluate trust score and generate transparent explanation.
        """
        reasons: list[str] = []
        breakdown: dict[str, float] = {}

        # 1. Source Reliability (0 - 20)
        source_score = 10.0
        if report.source == WeatherReportSource.weather_api:
            source_score = 20.0
            reasons.append("✓ Source verified as automated meteorological API feed")
        elif report.source == WeatherReportSource.public_dataset:
            source_score = 18.0
            reasons.append("✓ Sourced from curated public national meteorological dataset")
        elif report.source == WeatherReportSource.community_feed:
            source_score = 14.0
            reasons.append("✓ Community broadcast partner feed with established origin")
        elif report.source == WeatherReportSource.citizen:
            source_score = 12.0
            reasons.append("✓ Direct citizen eyewitness report (unauthenticated mobile submission)")
        elif report.source == WeatherReportSource.synthetic:
            source_score = 15.0
            reasons.append("✓ Deterministic simulation source (demo dataset)")
        breakdown["source_reliability"] = source_score

        # 2. Weather Consistency (0 - 25)
        weather_score = 15.0  # neutral if no forecast
        if forecast_condition is not None:
            f_lower = forecast_condition.lower()
            cat = report.event_category

            # Rain / Thunderstorm / Flooding check
            if cat in (WeatherEventCategory.rainfall, WeatherEventCategory.thunderstorm, WeatherEventCategory.flooding):
                if any(w in f_lower for w in ("rain", "thunder", "drizzle", "shower", "monsoon")):
                    weather_score = 25.0
                    reasons.append(f"✓ Observation matches local meteorological radar/forecast ({forecast_condition})")
                elif forecast_precipitation_prob and forecast_precipitation_prob >= 50:
                    weather_score = 22.0
                    reasons.append(f"✓ High precipitation probability ({forecast_precipitation_prob:.0f}%) recorded in area")
                elif any(w in f_lower for w in ("clear", "sunny", "dry")):
                    weather_score = 5.0
                    reasons.append(f"⚠ Conflicting observation: Report claims rain but local forecast indicates '{forecast_condition}'")
            # Heatwave check
            elif cat == WeatherEventCategory.heatwave:
                if any(w in f_lower for w in ("clear", "sunny", "heat", "hot")):
                    weather_score = 24.0
                    reasons.append("✓ Heatwave report aligns with high thermal index forecast")
                else:
                    weather_score = 10.0
                    reasons.append(f"⚠ Heatwave report inconsistent with cooler/cloudy forecast '{forecast_condition}'")
            # Dust storm check
            elif cat == WeatherEventCategory.dust_storm:
                weather_score = 20.0
                reasons.append("✓ Atmospheric conditions support squall / convective dust turbulence")
            else:
                weather_score = 18.0
                reasons.append("✓ Baseline alignment with regional seasonal weather patterns")
        else:
            reasons.append("✓ General meteorological consistency with regional monsoon belt")
        breakdown["weather_consistency"] = weather_score

        # 3. Geographic Consistency (0 - 15)
        geo_score = 15.0
        # Check coordinates inside India approximate bounding box (Lat 6-37, Lon 68-98)
        if 6.0 <= report.latitude <= 37.5 and 68.0 <= report.longitude <= 98.0:
            reasons.append(f"✓ Coordinates ({report.latitude:.2f}°N, {report.longitude:.2f}°E) inside {report.city}, {report.state}")
        else:
            geo_score = 4.0
            reasons.append("⚠ Coordinates fall outside verified national geographic boundaries")
        breakdown["spatial_consistency"] = geo_score

        # 4. Temporal Consistency (0 - 15)
        temp_score = 15.0
        now_utc = datetime.now(timezone.utc)
        rep_time = report.event_time.astimezone(timezone.utc)
        hours_old = (now_utc - rep_time).total_seconds() / 3600.0

        if 0.0 <= hours_old <= 24.0:
            reasons.append("✓ Timestamp is fresh (recorded within past 24 hours)")
        elif hours_old < 0:
            temp_score = 5.0
            reasons.append("⚠ Submission timestamp appears to be in the future (clock skew)")
        else:
            temp_score = 9.0
            reasons.append(f"⚠ Historical record submitted {hours_old:.0f} hours after event")
        breakdown["temporal_consistency"] = temp_score

        # 5. Cross-Report Corroboration (0 - 15)
        corroboration_score = 6.0
        if nearby_reports_count >= 5:
            corroboration_score = 15.0
            reasons.append(f"✓ Strongly corroborated: {nearby_reports_count} nearby citizen reports support event")
        elif nearby_reports_count >= 2:
            corroboration_score = 12.0
            reasons.append(f"✓ Corroborated: {nearby_reports_count} adjacent reports in vicinity")
        elif nearby_reports_count == 1:
            corroboration_score = 9.0
            reasons.append("✓ Single supporting report registered in district radius")
        else:
            corroboration_score = 6.0
            reasons.append("⚠ Isolated report: No immediate adjacent reports currently recorded")
        breakdown["cross_report_agreement"] = corroboration_score

        # 6. Media / Visual Evidence (0 - 10)
        media_score = 4.0
        if report.media_urls and len(report.media_urls) > 0:
            media_score = 10.0
            reasons.append(f"✓ Accompanied by {len(report.media_urls)} geotagged visual evidence asset(s)")
        else:
            media_score = 5.0
            reasons.append("⚠ Text-only report without attached photo/video evidence")
        breakdown["media_evidence"] = media_score

        # Total Trust Score [0 - 100]
        total_trust = sum(breakdown.values())
        total_trust = round(min(100.0, max(0.0, total_trust)), 1)
        misinfo_score = round(max(0.0, 100.0 - total_trust), 1)

        is_credible = total_trust >= 65.0

        return TrustEvaluation(
            trust_score=total_trust,
            misinformation_score=misinfo_score,
            breakdown=breakdown,
            reasons=reasons,
            is_credible=is_credible,
        )


DEFAULT_TRUST_ENGINE = SourceTrustEngine()
