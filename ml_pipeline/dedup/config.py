"""
ml_pipeline/dedup/config.py — Deduplication Engine Configuration

Thresholds and parameters governing candidate filtering, text similarity,
perceptual image hashing, and duplicate decision logic.

IMPORTANT / DATA INTEGRITY NOTE:
All threshold default values here are heuristic engineering defaults designed
for this hackathon MVP based on standard perceptual hashing and geospatial
clustering practices. They are NOT scientifically calibrated or ground-truth
validated constants. All values can be overridden via environment variables
or by passing a custom DedupConfig instance.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DedupConfig:
    """
    Configuration for the multi-modal deduplication pipeline.

    Attributes:
        TEXT_SIMILARITY_THRESHOLD:
            Minimum cosine similarity between sentence embeddings [0.0, 1.0]
            for two descriptions to be considered semantically near-duplicate.
            Default: 0.78.
            Heuristic rationale: Below 0.75, descriptions frequently diverge into
            different damage characteristics (e.g. glass vs foundation); above 0.85,
            minor phrasing changes from different bystanders are missed.

        IMAGE_HASH_DISTANCE_THRESHOLD:
            Maximum Hamming distance (bit difference out of 64) between pHash
            perceptual hashes to consider two images identical or near-duplicate.
            Default: 10.
            Heuristic rationale: Identical images have distance 0; standard JPEG
            recompression, slight crops, or watermarking typically yield distance
            <= 8-10. Visually distinct photos of different buildings yield >= 20.

        SPATIAL_DISTANCE_THRESHOLD_KM:
            Maximum Haversine distance in kilometers between two report coordinates
            for them to be considered candidate duplicates of the same physical structure.
            Default: 1.0 km.
            Heuristic rationale: Citizen GPS accuracy in urban canyons is typically
            within 50-100m, but users often drop pins nearby or report while moving.
            1.0 km groups reports for the same neighborhood/block while isolating
            incidents across distinct city wards.

        TEMPORAL_WINDOW_MINUTES:
            Maximum time delta in minutes between two reports for them to be considered
            candidates for the same immediate incident.
            Default: 180.0 minutes (3 hours).
            Heuristic rationale: Citizen eyewitness reporting spikes heavily in the
            first 2-3 hours following a major earthquake shock or aftershock.

        FALLBACK_IMAGE_MAX_BITS:
            Total bits in the perceptual hash (64 for 8x8 pHash).
    """

    TEXT_SIMILARITY_THRESHOLD: float = field(
        default_factory=lambda: float(
            os.getenv("DEDUP_TEXT_SIMILARITY_THRESHOLD", "0.78")
        )
    )
    IMAGE_HASH_DISTANCE_THRESHOLD: int = field(
        default_factory=lambda: int(
            os.getenv("DEDUP_IMAGE_HASH_DISTANCE_THRESHOLD", "10")
        )
    )
    SPATIAL_DISTANCE_THRESHOLD_KM: float = field(
        default_factory=lambda: float(
            os.getenv("DEDUP_SPATIAL_DISTANCE_THRESHOLD_KM", "1.0")
        )
    )
    TEMPORAL_WINDOW_MINUTES: float = field(
        default_factory=lambda: float(
            os.getenv("DEDUP_TEMPORAL_WINDOW_MINUTES", "180.0")
        )
    )
    FALLBACK_IMAGE_MAX_BITS: int = 64


# Default singleton configuration
DEFAULT_DEDUP_CONFIG = DedupConfig()
