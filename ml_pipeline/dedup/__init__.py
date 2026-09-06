"""
ml_pipeline/dedup — Multi-Modal Deduplication Package

Modules:
- config: Thresholds and parameters for candidate filtering and similarity scoring.
- image_dedup: Perceptual image hashing (pHash) and Hamming distance comparison.
- text_dedup: Lightweight semantic text embedding and cosine similarity.
- candidate_filter: Spatial and temporal pre-filtering to reduce pairwise comparisons.
- near_duplicate: Multi-modal duplicate decision engine and canonical clustering.
- run: CLI service runner for database deduplication.
"""

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
    is_duplicate_image,
)
from ml_pipeline.dedup.near_duplicate import (
    DeduplicationSummary,
    DuplicateResult,
    cluster_and_resolve_duplicates,
    deduplicate_reports,
    evaluate_duplicate_pair,
)
from ml_pipeline.dedup.text_dedup import (
    embed_texts,
    get_sentence_transformer_model,
    text_similarity,
)

__all__ = [
    "DedupConfig",
    "DEFAULT_DEDUP_CONFIG",
    "compute_image_hash",
    "compare_image_hashes",
    "image_similarity_score",
    "is_duplicate_image",
    "get_sentence_transformer_model",
    "embed_texts",
    "text_similarity",
    "haversine_distance_km",
    "temporal_difference_minutes",
    "CandidatePair",
    "generate_candidate_pairs",
    "DuplicateResult",
    "DeduplicationSummary",
    "evaluate_duplicate_pair",
    "cluster_and_resolve_duplicates",
    "deduplicate_reports",
]
