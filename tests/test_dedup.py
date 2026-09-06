"""
tests/test_dedup.py — Multi-Modal Deduplication Pipeline Test Suite

Covers:
1. Group A-E deliberate benchmark fixtures with explicitly defined ground truth.
2. Perceptual image hashing (exact, resized, recompressed, different, missing, invalid).
3. Semantic text similarity (identical, paraphrased, unrelated, empty/None).
4. Candidate filtering (spatial, temporal, earthquake event matching).
5. Duplicate decision engine (obvious duplicates, non-duplicates, conflicting signals).
6. Canonical report resolution & clustering (earliest election, evidence preservation).
7. Database persistence of duplicate_of.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw

from backend.db.models import ReportORM
from backend.db.session import engine_from_url, get_session
from ingestion.schemas import DamageSeverity, DamageType, NormalizedReport, ReportSource, VerificationStatus
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


# ---------------------------------------------------------------------------
# Helper to create test images in memory or as temporary files
# ---------------------------------------------------------------------------

def _create_test_image(pattern: str = "gradient", color: str = "red", size: tuple[int, int] = (100, 100)) -> bytes:
    """Generate in-memory PNG bytes with texture for robust perceptual hashing."""
    import numpy as np

    if pattern == "noise":
        np.random.seed(42 if color == "red" else 99)
        arr = np.random.randint(0, 255, (size[1], size[0], 3), dtype=np.uint8)
        img = Image.fromarray(arr)
    elif pattern == "gradient":
        grad = np.tile(np.linspace(0, 255, size[0], dtype=np.uint8), (size[1], 1))
        img = Image.fromarray(grad).convert("RGB")
    elif pattern == "checker":
        img = Image.new("RGB", size, color="white")
        draw = ImageDraw.Draw(img)
        for x in range(0, size[0], 10):
            for y in range(0, size[1], 10):
                if (x // 10 + y // 10) % 2 == 0:
                    draw.rectangle([x, y, x + 10, y + 10], fill="black")
    else:
        img = Image.new("RGB", size, color=color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Deliberately Constructed Test Fixture (Groups A - E)
# ---------------------------------------------------------------------------

def create_benchmark_groups(tmp_path: Path) -> dict[str, list[dict[str, Any]]]:
    """
    Constructs the 5 canonical test groups with explicitly defined expectations:
    - Group A: Same image, same text, same location -> DUPLICATE
    - Group B: Same image, slightly modified text, nearby location -> DUPLICATE
    - Group C: Different image, semantically similar text, nearby location -> DUPLICATE
    - Group D: Same generic words but different incident/location (>500km) -> NOT DUPLICATE
    - Group E: Completely unrelated reports -> NOT DUPLICATE
    """
    t0 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)

    # Save images to disk to test file reference resolution
    img_a_bytes = _create_test_image("checker", "red")
    img_c1_bytes = _create_test_image("gradient", "green")
    img_c2_bytes = _create_test_image("noise", "blue")

    img_a_path = str(tmp_path / "img_a.png")
    img_c1_path = str(tmp_path / "img_c1.png")
    img_c2_path = str(tmp_path / "img_c2.png")

    Path(img_a_path).write_bytes(img_a_bytes)
    Path(img_c1_path).write_bytes(img_c1_bytes)
    Path(img_c2_path).write_bytes(img_c2_bytes)

    groups = {
        "GroupA": [
            {
                "report_id": uuid.uuid4(),
                "latitude": 28.6139,
                "longitude": 77.2090,
                "submitted_at": t0,
                "earthquake_event_id": "us_delhi_2026",
                "text": "Ground floor masonry wall collapsed completely at Gandhi Road commercial building",
                "image_reference": img_a_path,
            },
            {
                "report_id": uuid.uuid4(),
                "latitude": 28.6139,
                "longitude": 77.2090,
                "submitted_at": t0 + timedelta(minutes=5),
                "earthquake_event_id": "us_delhi_2026",
                "text": "Ground floor masonry wall collapsed completely at Gandhi Road commercial building",
                "image_reference": img_a_path,
            },
        ],
        "GroupB": [
            {
                "report_id": uuid.uuid4(),
                "latitude": 28.6142,
                "longitude": 77.2093,
                "submitted_at": t0 + timedelta(minutes=10),
                "earthquake_event_id": "us_delhi_2026",
                "text": "Heavy diagonal shear cracking on columns of City Hospital east wing",
                "image_reference": img_a_path,
            },
            {
                "report_id": uuid.uuid4(),
                "latitude": 28.6145,  # ~45 meters away
                "longitude": 77.2096,
                "submitted_at": t0 + timedelta(minutes=25),
                "earthquake_event_id": "us_delhi_2026",
                "text": "Major diagonal cracks observed on pillars at the hospital east wing",
                "image_reference": img_a_path,
            },
        ],
        "GroupC": [
            {
                "report_id": uuid.uuid4(),
                "latitude": 28.6140,
                "longitude": 77.2088,
                "submitted_at": t0 + timedelta(minutes=15),
                "earthquake_event_id": "us_delhi_2026",
                "text": "School boundary wall collapsed onto sidewalk blocking pedestrian passage",
                "image_reference": img_c1_path,
            },
            {
                "report_id": uuid.uuid4(),
                "latitude": 28.6143,  # ~35 meters away
                "longitude": 77.2091,
                "submitted_at": t0 + timedelta(minutes=30),
                "earthquake_event_id": "us_delhi_2026",
                "text": "School boundary wall has fallen down on the walkway obstructing people",
                "image_reference": img_c2_path,
            },
        ],
        "GroupD": [
            {
                "report_id": uuid.uuid4(),
                "latitude": 28.6139,
                "longitude": 77.2090,  # Delhi
                "submitted_at": t0 + timedelta(minutes=10),
                "earthquake_event_id": "us_delhi_2026",
                "text": "Earthquake damage observed on concrete building structure with cracked plaster",
                "image_reference": img_a_path,
            },
            {
                "report_id": uuid.uuid4(),
                "latitude": 23.2420,  # Bhuj (~900 km away!)
                "longitude": 69.6669,
                "submitted_at": t0 + timedelta(minutes=15),
                "earthquake_event_id": "us_bhuj_2026",
                "text": "Earthquake damage observed on concrete building structure with cracked plaster",
                "image_reference": img_c1_path,
            },
        ],
        "GroupE": [
            {
                "report_id": uuid.uuid4(),
                "latitude": 28.6139,
                "longitude": 77.2090,
                "submitted_at": t0,
                "earthquake_event_id": "us_delhi_2026",
                "text": "Severe collapse of roof tiles and chimney at heritage bungalow",
                "image_reference": img_c1_path,
            },
            {
                "report_id": uuid.uuid4(),
                "latitude": 28.5700,  # ~5 km away
                "longitude": 77.2200,
                "submitted_at": t0 + timedelta(hours=5),  # 5 hours later
                "earthquake_event_id": "us_delhi_2026",
                "text": "Minor water pipe leakage in basement car parking area",
                "image_reference": img_c2_path,
            },
        ],
    }
    return groups


@pytest.fixture
def dedup_benchmark_groups(tmp_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Pytest fixture returning the 5 benchmark groups."""
    return create_benchmark_groups(tmp_path)


# ---------------------------------------------------------------------------
# 1. Image Deduplication Unit Tests
# ---------------------------------------------------------------------------

class TestImageDeduplication:
    """Unit tests for image perceptual hashing and comparison."""

    def test_exact_duplicate_image(self):
        img_bytes = _create_test_image("checker", "red")
        h1 = compute_image_hash(img_bytes)
        h2 = compute_image_hash(img_bytes)

        assert h1 is not None
        assert h2 is not None
        dist = compare_image_hashes(h1, h2)
        assert dist == 0
        assert is_duplicate_image(h1, h2, threshold=DEFAULT_DEDUP_CONFIG.IMAGE_HASH_DISTANCE_THRESHOLD)
        assert image_similarity_score(h1, h2) == 1.0

    def test_resized_duplicate_image(self):
        img = Image.new("RGB", (200, 200), color="blue")
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, 180, 180], fill="white")

        h_orig = compute_image_hash(img)

        # Resized down to 64x64
        img_resized = img.resize((64, 64))
        h_resized = compute_image_hash(img_resized)

        dist = compare_image_hashes(h_orig, h_resized)
        assert dist is not None
        assert dist <= DEFAULT_DEDUP_CONFIG.IMAGE_HASH_DISTANCE_THRESHOLD
        assert is_duplicate_image(h_orig, h_resized)

    def test_recompressed_duplicate_image(self):
        img_bytes = _create_test_image("gradient", "green", size=(150, 150))
        h_orig = compute_image_hash(img_bytes)

        # Compress to low-quality JPEG
        with Image.open(io.BytesIO(img_bytes)) as img:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=60)
            h_jpeg = compute_image_hash(buf.getvalue())

        dist = compare_image_hashes(h_orig, h_jpeg)
        assert dist is not None
        assert dist <= DEFAULT_DEDUP_CONFIG.IMAGE_HASH_DISTANCE_THRESHOLD
        assert is_duplicate_image(h_orig, h_jpeg)

    def test_different_images_have_large_distance(self):
        img1 = _create_test_image("checker", "red")
        img2 = _create_test_image("noise", "blue")

        h1 = compute_image_hash(img1)
        h2 = compute_image_hash(img2)

        dist = compare_image_hashes(h1, h2)
        assert dist is not None
        assert dist > DEFAULT_DEDUP_CONFIG.IMAGE_HASH_DISTANCE_THRESHOLD
        assert not is_duplicate_image(h1, h2)

    def test_missing_image_returns_none(self):
        assert compute_image_hash(None) is None
        assert compute_image_hash("") is None
        assert compute_image_hash("   ") is None
        assert compute_image_hash("/path/does/not/exist.jpg") is None
        assert compare_image_hashes(None, None) is None
        assert is_duplicate_image(None, None) is False
        assert image_similarity_score(None, None) is None

    def test_invalid_image_file_returns_none_gracefully(self, tmp_path: Path):
        corrupt_file = tmp_path / "corrupt.jpg"
        corrupt_file.write_bytes(b"NOT_A_VALID_JPEG_HEADER_12345678")

        # Must not raise an exception
        result = compute_image_hash(str(corrupt_file))
        assert result is None


# ---------------------------------------------------------------------------
# 2. Text Deduplication Unit Tests
# ---------------------------------------------------------------------------

class TestTextDeduplication:
    """Unit tests for semantic text embedding and similarity."""

    def test_identical_text(self):
        t = "Major structural crack through reinforced concrete column"
        sim = text_similarity(t, t)
        assert sim == 1.0

    def test_paraphrased_near_duplicate_text(self):
        t1 = "Outer masonry wall collapsed on Gandhi Marg near the hospital"
        t2 = "Exterior brick wall fell down on Gandhi Marg close to hospital"
        sim = text_similarity(t1, t2)
        assert sim >= 0.75

    def test_unrelated_text(self):
        t1 = "Severe structural damage to bridge foundation beams"
        t2 = "Supermarket has opened a new grocery aisle with fresh fruits"
        sim = text_similarity(t1, t2)
        assert sim < 0.40

    def test_empty_and_none_text(self):
        t = "Column failure on ground floor"
        assert text_similarity(None, t) == 0.0
        assert text_similarity(t, None) == 0.0
        assert text_similarity("", t) == 0.0
        assert text_similarity(None, None) == 0.0
        assert text_similarity("   ", "   ") == 0.0

    def test_embed_texts_shape_and_norm(self):
        texts = [
            "Building collapse in Ahmedabad",
            "Cracked pillar in Bhuj school",
        ]
        embs = embed_texts(texts)
        assert embs.shape[0] == 2
        assert embs.shape[1] > 0
        # Check normalized vectors (norm ~ 1.0)
        norm = (embs[0] ** 2).sum()
        assert abs(norm - 1.0) < 1e-2


# ---------------------------------------------------------------------------
# 3. Candidate Filtering Unit Tests
# ---------------------------------------------------------------------------

class TestCandidateFiltering:
    """Unit tests for spatial and temporal candidate generation."""

    def test_haversine_formula_accuracy(self):
        # Delhi (28.6139, 77.2090) to Connaught Place (28.6315, 77.2167) ~ 2.1 km
        dist = haversine_distance_km(28.6139, 77.2090, 28.6315, 77.2167)
        assert 1.9 <= dist <= 2.3

        # Same point must be exactly 0.0
        assert haversine_distance_km(28.6139, 77.2090, 28.6139, 77.2090) == 0.0

    def test_temporal_difference_minutes(self):
        t1 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 4, 12, 15, 0, tzinfo=timezone.utc)
        assert temporal_difference_minutes(t1, t2) == 135.0

    def test_nearby_and_same_event_qualifies(self):
        t0 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
        r1 = {
            "report_id": "r1",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "submitted_at": t0,
            "earthquake_event_id": "ev1",
        }
        r2 = {
            "report_id": "r2",
            "latitude": 28.6145,  # ~70m away
            "longitude": 77.2092,
            "submitted_at": t0 + timedelta(minutes=15),
            "earthquake_event_id": "ev1",
        }

        candidates = generate_candidate_pairs([r1, r2])
        assert len(candidates) == 1
        assert candidates[0].id_a == "r1"
        assert candidates[0].id_b == "r2"
        assert candidates[0].same_event is True

    def test_far_away_pruned(self):
        t0 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
        r1 = {
            "report_id": "r1",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "submitted_at": t0,
            "earthquake_event_id": "ev1",
        }
        r2 = {
            "report_id": "r2",
            "latitude": 28.7000,  # ~10 km away
            "longitude": 77.2090,
            "submitted_at": t0,
            "earthquake_event_id": "ev1",
        }

        candidates = generate_candidate_pairs([r1, r2])
        assert len(candidates) == 0

    def test_outside_temporal_window_pruned(self):
        t0 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
        r1 = {
            "report_id": "r1",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "submitted_at": t0,
            "earthquake_event_id": "ev1",
        }
        r2 = {
            "report_id": "r2",
            "latitude": 28.6140,
            "longitude": 77.2090,
            "submitted_at": t0 + timedelta(hours=4),  # 240 min > 180 min window
            "earthquake_event_id": "ev1",
        }

        candidates = generate_candidate_pairs([r1, r2])
        assert len(candidates) == 0

    def test_conflicting_events_pruned(self):
        t0 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
        r1 = {
            "report_id": "r1",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "submitted_at": t0,
            "earthquake_event_id": "event_alpha",
        }
        r2 = {
            "report_id": "r2",
            "latitude": 28.6140,
            "longitude": 77.2090,
            "submitted_at": t0,
            "earthquake_event_id": "event_beta",
        }

        candidates = generate_candidate_pairs([r1, r2])
        assert len(candidates) == 0

    def test_missing_event_id_allowed_if_nearby(self):
        t0 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
        r1 = {
            "report_id": "r1",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "submitted_at": t0,
            "earthquake_event_id": None,
        }
        r2 = {
            "report_id": "r2",
            "latitude": 28.6140,
            "longitude": 77.2090,
            "submitted_at": t0 + timedelta(minutes=5),
            "earthquake_event_id": "event_alpha",
        }

        candidates = generate_candidate_pairs([r1, r2])
        assert len(candidates) == 1


# ---------------------------------------------------------------------------
# 4. Decision Engine Benchmark Group Tests (Groups A - E)
# ---------------------------------------------------------------------------

class TestDecisionEngineGroups:
    """Benchmark tests validating the 5 explicit test fixture groups."""

    def test_group_a_same_image_same_text_same_location(self, dedup_benchmark_groups):
        """Group A must be recognized as duplicate with same_image_and_nearby_location."""
        reports = dedup_benchmark_groups["GroupA"]
        res = evaluate_duplicate_pair(reports[0], reports[1])

        assert res.is_duplicate is True
        assert res.reason == "same_image_and_nearby_location"
        assert res.confidence >= 0.85
        assert res.spatial_distance_km <= 0.05

    def test_group_b_same_image_paraphrased_text_nearby(self, dedup_benchmark_groups):
        """Group B has the same image and paraphrased text nearby -> DUPLICATE."""
        reports = dedup_benchmark_groups["GroupB"]
        res = evaluate_duplicate_pair(reports[0], reports[1])

        assert res.is_duplicate is True
        assert res.reason in ("same_image_and_nearby_location", "high_text_similarity_and_same_event")
        assert res.confidence >= 0.80

    def test_group_c_different_image_similar_text_nearby(self, dedup_benchmark_groups):
        """Group C has different images but high semantic text similarity nearby -> DUPLICATE."""
        reports = dedup_benchmark_groups["GroupC"]
        res = evaluate_duplicate_pair(reports[0], reports[1])

        assert res.is_duplicate is True
        assert res.reason == "high_text_similarity_and_same_event"
        assert res.text_similarity is not None and res.text_similarity >= DEFAULT_DEDUP_CONFIG.TEXT_SIMILARITY_THRESHOLD

    def test_group_d_generic_words_different_location(self, dedup_benchmark_groups):
        """Group D shares generic words ('earthquake damage') but is 900km away -> NOT DUPLICATE."""
        reports = dedup_benchmark_groups["GroupD"]
        res = evaluate_duplicate_pair(reports[0], reports[1])

        assert res.is_duplicate is False
        assert res.reason == "outside_spatial_threshold"
        assert res.spatial_distance_km > 100.0

    def test_group_e_unrelated_reports(self, dedup_benchmark_groups):
        """Group E has unrelated text, different images, and distance > 1km -> NOT DUPLICATE."""
        reports = dedup_benchmark_groups["GroupE"]
        res = evaluate_duplicate_pair(reports[0], reports[1])

        assert res.is_duplicate is False
        assert res.reason in ("outside_spatial_threshold", "outside_temporal_window", "not_duplicate")


# ---------------------------------------------------------------------------
# 5. Decision Engine Edge Cases & Missing Modalities
# ---------------------------------------------------------------------------

class TestDecisionEngineEdgeCases:
    """Tests for conflicting signals and missing modalities."""

    def test_conflicting_signals_same_image_but_far_away_rejected(self, tmp_path: Path):
        """A viral photo reported 500km away must NOT be merged as a single localized damage incident."""
        img_path = str(tmp_path / "shared.png")
        Path(img_path).write_bytes(_create_test_image("solid", "yellow"))

        t0 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
        r1 = {
            "report_id": uuid.uuid4(),
            "latitude": 28.6139,
            "longitude": 77.2090,  # Delhi
            "submitted_at": t0,
            "earthquake_event_id": "ev1",
            "image_reference": img_path,
        }
        r2 = {
            "report_id": uuid.uuid4(),
            "latitude": 19.0760,
            "longitude": 72.8777,  # Mumbai (>1100 km away)
            "submitted_at": t0 + timedelta(minutes=10),
            "earthquake_event_id": "ev1",
            "image_reference": img_path,
        }

        res = evaluate_duplicate_pair(r1, r2)
        assert res.is_duplicate is False
        assert res.reason == "outside_spatial_threshold"

    def test_missing_image_text_only_works(self):
        """When neither report has an image, deduplication proceeds purely on text + space/time."""
        t0 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
        r1 = {
            "report_id": uuid.uuid4(),
            "latitude": 28.6139,
            "longitude": 77.2090,
            "submitted_at": t0,
            "earthquake_event_id": "ev1",
            "text": "Staircase collapsed on building rear side, people trapped on second floor",
            "image_reference": None,
        }
        r2 = {
            "report_id": uuid.uuid4(),
            "latitude": 28.6141,
            "longitude": 77.2091,
            "submitted_at": t0 + timedelta(minutes=5),
            "earthquake_event_id": "ev1",
            "text": "Rear staircase collapse on building, residents stuck on second floor",
            "image_reference": None,
        }

        res = evaluate_duplicate_pair(r1, r2)
        assert res.is_duplicate is True
        assert res.image_hash_distance is None
        assert res.text_similarity is not None and res.text_similarity >= 0.78
        assert res.reason == "high_text_similarity_and_same_event"

    def test_missing_text_image_only_works(self, tmp_path: Path):
        """When reports lack descriptions, deduplication succeeds on perceptual image match + location."""
        img_path = str(tmp_path / "img.png")
        Path(img_path).write_bytes(_create_test_image("checker", "cyan"))

        t0 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
        r1 = {
            "report_id": uuid.uuid4(),
            "latitude": 28.6139,
            "longitude": 77.2090,
            "submitted_at": t0,
            "earthquake_event_id": "ev1",
            "text": None,
            "image_reference": img_path,
        }
        r2 = {
            "report_id": uuid.uuid4(),
            "latitude": 28.6142,
            "longitude": 77.2092,
            "submitted_at": t0 + timedelta(minutes=10),
            "earthquake_event_id": "ev1",
            "text": None,
            "image_reference": img_path,
        }

        res = evaluate_duplicate_pair(r1, r2)
        assert res.is_duplicate is True
        assert res.text_similarity == 0.0
        assert res.image_hash_distance == 0
        assert res.reason == "same_image_and_nearby_location"


# ---------------------------------------------------------------------------
# 6. Canonical Resolution & Clustering Tests
# ---------------------------------------------------------------------------

class TestCanonicalResolution:
    """Tests for electing canonical reports and clustering."""

    def test_canonical_elected_by_earliest_timestamp(self):
        t0 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
        id_first = uuid.uuid4()
        id_second = uuid.uuid4()
        id_third = uuid.uuid4()

        r1 = {"report_id": id_first, "submitted_at": t0}
        r2 = {"report_id": id_second, "submitted_at": t0 + timedelta(minutes=5)}
        r3 = {"report_id": id_third, "submitted_at": t0 + timedelta(minutes=10)}

        results = [
            DuplicateResult(
                is_duplicate=True,
                confidence=0.90,
                spatial_distance_km=0.05,
                temporal_distance_minutes=5.0,
                reason="high_text_similarity_and_same_event",
                report_a_id=id_first,
                report_b_id=id_second,
            ),
            DuplicateResult(
                is_duplicate=True,
                confidence=0.90,
                spatial_distance_km=0.08,
                temporal_distance_minutes=10.0,
                reason="high_text_similarity_and_same_event",
                report_a_id=id_second,
                report_b_id=id_third,
            ),
        ]

        summary, dup_map = cluster_and_resolve_duplicates([r1, r2, r3], results)

        assert summary.reports_processed == 3
        assert summary.canonical_reports == 1
        assert summary.duplicate_reports == 2
        # r1 was earliest -> canonical
        assert dup_map[str(id_first)] is None
        # r2 and r3 both point to r1
        assert dup_map[str(id_second)] == id_first
        assert dup_map[str(id_third)] == id_first

    def test_original_evidence_preserved(self, dedup_benchmark_groups):
        """Original evidence, coordinates, and texts must not be modified or erased."""
        reports = dedup_benchmark_groups["GroupA"]
        original_texts = [r["text"] for r in reports]
        original_coords = [(r["latitude"], r["longitude"]) for r in reports]

        summary, dup_map = deduplicate_reports(reports)

        assert summary.canonical_reports == 1
        assert summary.duplicate_reports == 1

        # Check raw inputs still intact
        for i, r in enumerate(reports):
            assert r["text"] == original_texts[i]
            assert (r["latitude"], r["longitude"]) == original_coords[i]


# ---------------------------------------------------------------------------
# 7. Database Persistence Tests
# ---------------------------------------------------------------------------

class TestDatabaseDeduplication:
    """Tests for persisting duplicate_of into the reports table."""

    def test_duplicate_of_persisted_in_db(self):
        """
        Inserts 2 duplicate test reports into PostgreSQL/PostGIS, runs
        the deduplication runner, and verifies duplicate_of is updated
        while the canonical report retains duplicate_of=None.
        """
        import os

        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql://sih_user:sih_password@localhost:5432/disaster_db",
        )

        try:
            with get_session(db_url) as session:
                t0 = datetime(2026, 9, 4, 11, 0, 0, tzinfo=timezone.utc)
                id_can = uuid.uuid4()
                id_dup = uuid.uuid4()

                r_can = ReportORM(
                    report_id=id_can,
                    source=ReportSource.synthetic,
                    submitted_at=t0,
                    latitude=28.6139,
                    longitude=77.2090,
                    geometry=f"SRID=4326;POINT(77.2090 28.6139)",
                    location_text="Connaught Place, New Delhi",
                    text="Extensive facade cracking and glass shattered on commercial high-rise building",
                    earthquake_event_id=None,
                    damage_type=DamageType.unknown,
                    severity=DamageSeverity.unknown,
                    verification_status=VerificationStatus.pending,
                    is_synthetic=True,
                )

                r_dup = ReportORM(
                    report_id=id_dup,
                    source=ReportSource.synthetic,
                    submitted_at=t0 + timedelta(minutes=8),
                    latitude=28.6142,  # ~35m away
                    longitude=77.2092,
                    geometry=f"SRID=4326;POINT(77.2092 28.6142)",
                    location_text="Connaught Place, New Delhi",
                    text="Glass shattered and extensive facade cracking on commercial high-rise building",
                    earthquake_event_id=None,
                    damage_type=DamageType.unknown,
                    severity=DamageSeverity.unknown,
                    verification_status=VerificationStatus.pending,
                    is_synthetic=True,
                )

                session.add(r_can)
                session.add(r_dup)
                session.commit()

                # Run deduplication on these two
                summary, dup_map = deduplicate_reports([r_can, r_dup])

                assert summary.duplicate_pairs == 1
                assert dup_map[str(id_can)] is None
                assert dup_map[str(id_dup)] == id_can

                # Apply to DB
                r_can.duplicate_of = dup_map[str(id_can)]
                r_dup.duplicate_of = dup_map[str(id_dup)]
                session.commit()

                # Re-query from DB to verify persistence
                saved_can = session.query(ReportORM).filter_by(report_id=id_can).one()
                saved_dup = session.query(ReportORM).filter_by(report_id=id_dup).one()

                assert saved_can.duplicate_of is None
                assert saved_dup.duplicate_of == id_can
                # Confirm original texts and locations preserved
                assert saved_dup.text == r_dup.text
                assert saved_dup.latitude == r_dup.latitude

                # Clean up test rows
                session.delete(saved_can)
                session.delete(saved_dup)
                session.commit()

        except Exception as exc:
            pytest.skip(f"Database not available for integration test: {exc}")


# ---------------------------------------------------------------------------
# Callable Demo Function for Test Fixture
# ---------------------------------------------------------------------------

def run_fixture_demo() -> DeduplicationSummary:
    """Run demonstration across all 5 benchmark groups."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        groups = create_benchmark_groups(Path(tmpdir))
        all_reports = []
        for g_name, r_list in groups.items():
            all_reports.extend(r_list)

        print(f"\n--- Running Deduplication on Benchmark Fixture ({len(all_reports)} reports across 5 groups) ---")
        summary, dup_map = deduplicate_reports(all_reports)

        print(f"Total reports: {summary.reports_processed}")
        print(f"Candidate pairs evaluated: {summary.candidate_pairs}")
        print(f"Duplicate pairs identified: {summary.duplicate_pairs}")
        print(f"Canonical reports elected: {summary.canonical_reports}")
        print(f"Duplicate reports merged: {summary.duplicate_reports}")
        for res in summary.results:
            status = "DUPLICATE" if res.is_duplicate else "DISTINCT"
            print(f"  [{status}] reason={res.reason} (conf={res.confidence}, dist={res.spatial_distance_km}km, dt={res.temporal_distance_minutes}m)")

        return summary
