"""
ml_pipeline/dedup/near_duplicate.py — Multi-Modal Duplicate Decision Engine

Combines perceptual image hashing, semantic text similarity, spatial distance,
and temporal windowing to make explainable duplicate/non-duplicate decisions.
Provides deterministic canonical report clustering while preserving 100% of raw evidence.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from ml_pipeline.dedup.candidate_filter import (
    CandidatePair,
    generate_candidate_pairs,
    haversine_distance_km,
    temporal_difference_minutes,
)
from ml_pipeline.dedup.config import DEFAULT_DEDUP_CONFIG, DedupConfig
from ml_pipeline.dedup.image_dedup import (
    compare_image_hashes,
    compute_image_hash,
    image_similarity_score,
)
from ml_pipeline.dedup.text_dedup import text_similarity

logger = logging.getLogger(__name__)


class DuplicateResult(BaseModel):
    """
    Structured outcome of evaluating a pair of reports for duplication.

    IMPORTANT / DATA INTEGRITY RULE:
    `confidence` represents the heuristic certainty of the deduplication decision rule
    (e.g., 0.95 for exact image hash match within 50 meters), NOT a calibrated
    probability of physical damage or an unvalidated statistical claim.
    """

    is_duplicate: bool = Field(
        ...,
        description="True if the reports describe the same incident and should be deduplicated.",
    )
    duplicate_of: Optional[uuid.UUID] = Field(
        default=None,
        description="UUID of the canonical report if is_duplicate is True, else None.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Heuristic deduplication decision confidence score [0.0, 1.0].",
    )
    text_similarity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Cosine similarity between text embeddings [0.0, 1.0], or None if missing.",
    )
    image_similarity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Normalized perceptual image similarity [0.0, 1.0], or None if missing.",
    )
    image_hash_distance: Optional[int] = Field(
        default=None,
        ge=0,
        le=64,
        description="Hamming bit distance between perceptual hashes (0-64), or None if missing.",
    )
    spatial_distance_km: float = Field(
        ...,
        ge=0.0,
        description="Great-circle Haversine distance in kilometers.",
    )
    temporal_distance_minutes: float = Field(
        ...,
        ge=0.0,
        description="Absolute time difference in minutes between submissions.",
    )
    reason: str = Field(
        ...,
        description="Auditable explanation for the deduplication decision.",
    )
    report_a_id: Any = Field(default=None, description="Identifier of report A.")
    report_b_id: Any = Field(default=None, description="Identifier of report B.")


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Helper to get attribute from dict or object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def evaluate_duplicate_pair(
    report_a: Any,
    report_b: Any,
    spatial_dist_km: float | None = None,
    temporal_dist_min: float | None = None,
    config: DedupConfig = DEFAULT_DEDUP_CONFIG,
) -> DuplicateResult:
    """
    Evaluate whether two reports are duplicates of the same physical damage incident.

    Combines:
    1. Spatial proximity (Haversine distance <= SPATIAL_DISTANCE_THRESHOLD_KM)
    2. Temporal window (<= TEMPORAL_WINDOW_MINUTES)
    3. Perceptual image similarity (Hamming distance <= IMAGE_HASH_DISTANCE_THRESHOLD)
    4. Semantic text similarity (cosine similarity >= TEXT_SIMILARITY_THRESHOLD)
    5. Multi-modal joint evidence

    Returns an explainable DuplicateResult with a concrete reason string.
    """
    id_a = _get_attr(report_a, "report_id", _get_attr(report_a, "id"))
    id_b = _get_attr(report_b, "report_id", _get_attr(report_b, "id"))

    # Compute distances if not already supplied
    if spatial_dist_km is None:
        lat_a = float(_get_attr(report_a, "latitude"))
        lon_a = float(_get_attr(report_a, "longitude"))
        lat_b = float(_get_attr(report_b, "latitude"))
        lon_b = float(_get_attr(report_b, "longitude"))
        spatial_dist_km = haversine_distance_km(lat_a, lon_a, lat_b, lon_b)

    if temporal_dist_min is None:
        sub_a = _get_attr(report_a, "submitted_at")
        sub_b = _get_attr(report_b, "submitted_at")
        if isinstance(sub_a, str):
            sub_a = datetime.fromisoformat(sub_a.replace("Z", "+00:00"))
        if isinstance(sub_b, str):
            sub_b = datetime.fromisoformat(sub_b.replace("Z", "+00:00"))
        temporal_dist_min = temporal_difference_minutes(sub_a, sub_b)

    event_a = _get_attr(report_a, "earthquake_event_id")
    event_b = _get_attr(report_b, "earthquake_event_id")
    same_event = bool(event_a and event_b and event_a == event_b)

    # 1. Spatial boundary check
    if spatial_dist_km > config.SPATIAL_DISTANCE_THRESHOLD_KM:
        return DuplicateResult(
            is_duplicate=False,
            duplicate_of=None,
            confidence=0.95,
            spatial_distance_km=spatial_dist_km,
            temporal_distance_minutes=temporal_dist_min,
            reason="outside_spatial_threshold",
            report_a_id=id_a,
            report_b_id=id_b,
        )

    # 2. Temporal boundary check
    if temporal_dist_min > config.TEMPORAL_WINDOW_MINUTES:
        return DuplicateResult(
            is_duplicate=False,
            duplicate_of=None,
            confidence=0.90,
            spatial_distance_km=spatial_dist_km,
            temporal_distance_minutes=temporal_dist_min,
            reason="outside_temporal_window",
            report_a_id=id_a,
            report_b_id=id_b,
        )

    # 3. Compute Image Similarity
    img_ref_a = _get_attr(report_a, "image_reference") or _get_attr(report_a, "image_path")
    img_ref_b = _get_attr(report_b, "image_reference") or _get_attr(report_b, "image_path")

    hash_a = compute_image_hash(img_ref_a) if img_ref_a else None
    hash_b = compute_image_hash(img_ref_b) if img_ref_b else None

    img_dist = compare_image_hashes(hash_a, hash_b)
    img_sim = image_similarity_score(hash_a, hash_b)

    # 4. Compute Text Similarity
    text_a = _get_attr(report_a, "text")
    text_b = _get_attr(report_b, "text")
    txt_sim = text_similarity(text_a, text_b)

    # 5. Multi-modal decision rules

    # Rule A: Perceptual image match (same or slightly modified image) + nearby location
    if img_dist is not None and img_dist <= config.IMAGE_HASH_DISTANCE_THRESHOLD:
        # Near-identical image in the same location is a conclusive duplicate
        conf = round(min(0.98, 0.88 + (1.0 - img_dist / float(config.IMAGE_HASH_DISTANCE_THRESHOLD)) * 0.10), 2)
        return DuplicateResult(
            is_duplicate=True,
            confidence=conf,
            text_similarity=txt_sim,
            image_similarity=img_sim,
            image_hash_distance=img_dist,
            spatial_distance_km=spatial_dist_km,
            temporal_distance_minutes=temporal_dist_min,
            reason="same_image_and_nearby_location",
            report_a_id=id_a,
            report_b_id=id_b,
        )

    # Rule B: High text semantic similarity + nearby location
    if txt_sim >= config.TEXT_SIMILARITY_THRESHOLD:
        conf = round(min(0.95, max(0.80, txt_sim * 0.95)), 2)
        return DuplicateResult(
            is_duplicate=True,
            confidence=conf,
            text_similarity=txt_sim,
            image_similarity=img_sim,
            image_hash_distance=img_dist,
            spatial_distance_km=spatial_dist_km,
            temporal_distance_minutes=temporal_dist_min,
            reason="high_text_similarity_and_same_event",
            report_a_id=id_a,
            report_b_id=id_b,
        )

    # Rule C: Joint multi-modal moderate evidence (both image and text moderately similar)
    if (
        img_dist is not None
        and img_dist <= 16
        and txt_sim >= 0.65
        and spatial_dist_km <= (config.SPATIAL_DISTANCE_THRESHOLD_KM * 0.5)
    ):
        return DuplicateResult(
            is_duplicate=True,
            confidence=0.82,
            text_similarity=txt_sim,
            image_similarity=img_sim,
            image_hash_distance=img_dist,
            spatial_distance_km=spatial_dist_km,
            temporal_distance_minutes=temporal_dist_min,
            reason="multimodal_similarity_and_nearby_location",
            report_a_id=id_a,
            report_b_id=id_b,
        )

    # Rule D: Nearby or same event, but insufficient similarity in both text and image
    if same_event or spatial_dist_km <= config.SPATIAL_DISTANCE_THRESHOLD_KM:
        conf = round(max(0.70, 1.0 - txt_sim), 2)
        return DuplicateResult(
            is_duplicate=False,
            confidence=conf,
            text_similarity=txt_sim,
            image_similarity=img_sim,
            image_hash_distance=img_dist,
            spatial_distance_km=spatial_dist_km,
            temporal_distance_minutes=temporal_dist_min,
            reason="same_event_but_insufficient_similarity",
            report_a_id=id_a,
            report_b_id=id_b,
        )

    # Rule E: Fallback unrelated
    return DuplicateResult(
        is_duplicate=False,
        confidence=0.99,
        text_similarity=txt_sim,
        image_similarity=img_sim,
        image_hash_distance=img_dist,
        spatial_distance_km=spatial_dist_km,
        temporal_distance_minutes=temporal_dist_min,
        reason="not_duplicate",
        report_a_id=id_a,
        report_b_id=id_b,
    )


class UnionFind:
    """Disjoint-set / Union-Find data structure for clustering duplicate reports."""

    def __init__(self, elements: list[str]) -> None:
        self.parent = {e: e for e in elements}

    def find(self, i: str) -> str:
        if self.parent[i] != i:
            self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i: str, j: str) -> None:
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            self.parent[root_i] = root_j


@dataclass
class DeduplicationSummary:
    """Measured summary of the deduplication pipeline run."""

    reports_processed: int
    candidate_pairs: int
    duplicate_pairs: int
    canonical_reports: int
    duplicate_reports: int
    clusters: list[list[str]]
    results: list[DuplicateResult]


def cluster_and_resolve_duplicates(
    reports: list[Any],
    duplicate_results: list[DuplicateResult],
) -> tuple[DeduplicationSummary, dict[str, uuid.UUID | None]]:
    """
    Cluster duplicate report pairs into connected components and select
    a deterministic canonical report for each cluster.

    Canonical Selection Rules:
    1. Earliest submission timestamp (`submitted_at`) is elected canonical.
    2. Deterministic tie-breaking using the lowest UUID string.
    3. Duplicate records have `duplicate_of` assigned to the canonical `report_id`.
    4. The canonical record keeps `duplicate_of = None`.
    5. Zero reports are deleted; all raw evidence and metadata are preserved.

    Returns:
        (DeduplicationSummary, {report_id_str: canonical_uuid_or_none})
    """
    report_map: dict[str, Any] = {}
    for r in reports:
        rid = str(_get_attr(r, "report_id", _get_attr(r, "id")))
        report_map[rid] = r

    all_ids = list(report_map.keys())
    uf = UnionFind(all_ids)

    # Union all pairs determined to be duplicates
    pos_results = [res for res in duplicate_results if res.is_duplicate]
    for res in pos_results:
        id_a = str(res.report_a_id)
        id_b = str(res.report_b_id)
        if id_a in report_map and id_b in report_map:
            uf.union(id_a, id_b)

    # Group into clusters by root
    clusters_by_root: dict[str, list[str]] = {}
    for rid in all_ids:
        root = uf.find(rid)
        clusters_by_root.setdefault(root, []).append(rid)

    duplicate_of_map: dict[str, uuid.UUID | None] = {}
    canonical_count = 0
    duplicate_count = 0
    multi_report_clusters: list[list[str]] = []

    for _, members in clusters_by_root.items():
        if len(members) == 1:
            # Singleton report is inherently canonical
            rid = members[0]
            duplicate_of_map[rid] = None
            canonical_count += 1
        else:
            multi_report_clusters.append(members)
            # Elect canonical report: earliest submitted_at, tie-break by UUID string
            def sort_key(member_id: str) -> tuple[datetime, str]:
                r = report_map[member_id]
                sub = _get_attr(r, "submitted_at")
                if isinstance(sub, str):
                    sub = datetime.fromisoformat(sub.replace("Z", "+00:00"))
                return (sub, member_id)

            sorted_members = sorted(members, key=sort_key)
            canonical_id = sorted_members[0]
            canonical_uuid = uuid.UUID(canonical_id)

            # Canonical report gets None
            duplicate_of_map[canonical_id] = None
            canonical_count += 1

            # All other members get duplicate_of = canonical_uuid
            for dup_id in sorted_members[1:]:
                duplicate_of_map[dup_id] = canonical_uuid
                duplicate_count += 1

    summary = DeduplicationSummary(
        reports_processed=len(reports),
        candidate_pairs=len(duplicate_results),
        duplicate_pairs=len(pos_results),
        canonical_reports=canonical_count,
        duplicate_reports=duplicate_count,
        clusters=multi_report_clusters,
        results=duplicate_results,
    )

    return summary, duplicate_of_map


def deduplicate_reports(
    reports: list[Any],
    config: DedupConfig = DEFAULT_DEDUP_CONFIG,
) -> tuple[DeduplicationSummary, dict[str, uuid.UUID | None]]:
    """
    End-to-end multi-modal deduplication pipeline over a list of reports.

    Steps:
    1. Candidate filtering (Spatial + Temporal + Event ID)
    2. Multi-modal pair evaluation (Image hashing + Semantic text similarity)
    3. Connected-component canonical resolution

    Returns:
        (DeduplicationSummary, duplicate_of_map)
    """
    candidates = generate_candidate_pairs(reports, config=config)

    results: list[DuplicateResult] = []
    for cand in candidates:
        res = evaluate_duplicate_pair(
            cand.report_a,
            cand.report_b,
            spatial_dist_km=cand.spatial_distance_km,
            temporal_dist_min=cand.temporal_distance_minutes,
            config=config,
        )
        results.append(res)

    summary, dup_map = cluster_and_resolve_duplicates(reports, results)
    return summary, dup_map
