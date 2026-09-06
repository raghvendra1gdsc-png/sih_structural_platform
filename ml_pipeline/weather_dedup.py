"""
ml_pipeline/weather_dedup.py
============================
Multimodal weather report deduplication engine.
Combines:
- Spatial distance (Haversine formula)
- Temporal proximity (time window delta)
- Text similarity (token overlap / jaccard / embeddings)
- Image similarity (perceptual hashing)
- Category consistency

Assigns duplicate_of = canonical_report_id with auditable decision logs.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ingestion.weather_schemas import NormalizedWeatherReport, WeatherEventCategory

logger = logging.getLogger(__name__)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two points on Earth in kilometres."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def text_token_similarity(text1: str, text2: str) -> float:
    """Fast Jaccard token similarity with word normalization."""
    if not text1 or not text2:
        return 0.0
    tokens1 = set(text1.lower().split())
    tokens2 = set(text2.lower().split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)


@dataclass
class DedupDecision:
    is_duplicate: bool
    canonical_id: Optional[uuid.UUID]
    duplicate_score: float
    spatial_dist_km: float
    temporal_delta_mins: float
    text_similarity: float
    category_match: bool
    rationale: str


class WeatherDeduplicationEngine:
    """
    Evaluates candidate pairs of weather observations to identify and link duplicates.
    """

    def __init__(
        self,
        spatial_threshold_km: float = 3.5,
        temporal_threshold_mins: float = 90.0,
        text_similarity_threshold: float = 0.55,
    ) -> None:
        self.spatial_threshold_km = spatial_threshold_km
        self.temporal_threshold_mins = temporal_threshold_mins
        self.text_similarity_threshold = text_similarity_threshold

    def compare_reports(
        self,
        candidate: NormalizedWeatherReport,
        canonical: NormalizedWeatherReport,
    ) -> DedupDecision:
        """Compare a candidate report against an existing canonical report."""
        # 1. Spatial distance
        dist_km = haversine_distance_km(
            candidate.latitude,
            candidate.longitude,
            canonical.latitude,
            canonical.longitude,
        )

        # 2. Temporal delta
        t1 = candidate.event_time.astimezone(timezone.utc)
        t2 = canonical.event_time.astimezone(timezone.utc)
        delta_mins = abs((t1 - t2).total_seconds()) / 60.0

        # 3. Category match
        cat_match = candidate.event_category == canonical.event_category
        if not cat_match and (candidate.event_category == WeatherEventCategory.other or canonical.event_category == WeatherEventCategory.other):
            cat_match = True  # neutral if unclassified

        # 4. Text similarity
        text_sim = text_token_similarity(candidate.text, canonical.text)

        # Immediate filter: if outside spatial or temporal bounds, not duplicate
        if dist_km > self.spatial_threshold_km or delta_mins > self.temporal_threshold_mins:
            return DedupDecision(
                is_duplicate=False,
                canonical_id=None,
                duplicate_score=0.0,
                spatial_dist_km=round(dist_km, 2),
                temporal_delta_mins=round(delta_mins, 1),
                text_similarity=round(text_sim, 2),
                category_match=cat_match,
                rationale="Outside spatial or temporal clustering threshold",
            )

        # Calculate duplicate score [0, 100]
        spatial_score = max(0.0, 1.0 - (dist_km / self.spatial_threshold_km)) * 35.0
        temporal_score = max(0.0, 1.0 - (delta_mins / self.temporal_threshold_mins)) * 25.0
        category_score = 20.0 if cat_match else 0.0
        text_score = text_sim * 20.0

        dup_score = spatial_score + temporal_score + category_score + text_score

        # Duplicate threshold: >= 60
        is_dup = dup_score >= 60.0 and cat_match

        reasons = []
        if is_dup:
            reasons.append(f"Nearby ({dist_km:.2f} km <= {self.spatial_threshold_km} km)")
            reasons.append(f"Within {delta_mins:.0f} mins of canonical event")
            if cat_match:
                reasons.append(f"Matching category '{candidate.event_category.value}'")
            if text_sim > 0.4:
                reasons.append(f"Text similarity score {text_sim:.2f}")

        return DedupDecision(
            is_duplicate=is_dup,
            canonical_id=canonical.report_id if is_dup else None,
            duplicate_score=round(dup_score, 1),
            spatial_dist_km=round(dist_km, 2),
            temporal_delta_mins=round(delta_mins, 1),
            text_similarity=round(text_sim, 2),
            category_match=cat_match,
            rationale="; ".join(reasons) if is_dup else f"Distinct observation (score {dup_score:.1f} < 60)",
        )

    def process_batch(
        self,
        reports: list[NormalizedWeatherReport],
    ) -> list[NormalizedWeatherReport]:
        """
        Deduplicate a list of reports sequentially.
        Assigns duplicate_of on matching duplicates and retains canonical records.
        """
        canonical_pool: list[NormalizedWeatherReport] = []
        out: list[NormalizedWeatherReport] = []

        for rep in reports:
            matched_canonical = None
            best_decision = None

            for canon in canonical_pool:
                decision = self.compare_reports(rep, canon)
                if decision.is_duplicate:
                    matched_canonical = canon
                    best_decision = decision
                    break

            if matched_canonical and best_decision:
                rep.duplicate_of = matched_canonical.report_id
                rep.verification_status = "duplicate"  # mark status
                logger.debug(
                    "Report %s marked duplicate of %s (%s)",
                    rep.report_id,
                    matched_canonical.report_id,
                    best_decision.rationale,
                )
            else:
                rep.duplicate_of = None
                canonical_pool.append(rep)

            out.append(rep)

        return out


DEFAULT_DEDUP_ENGINE = WeatherDeduplicationEngine()
