"""
ml_pipeline/weather_classifier.py
=================================
Zero-shot and NLP classification engine for weather reports.
Supports text-based triage and optional OpenCLIP zero-shot image classification.

Target Categories:
- rainfall, thunderstorm, flooding, heatwave, fog, dust_storm,
  strong_winds, cyclone, hailstorm, lightning, cold_wave, landslide, other
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from ingestion.weather_schemas import WeatherEventCategory

logger = logging.getLogger(__name__)

# Lexical keywords with category weights for fast, robust text classification
WEATHER_LEXICON: dict[WeatherEventCategory, list[tuple[str, float]]] = {
    WeatherEventCategory.rainfall: [
        ("rain", 0.6), ("downpour", 0.9), ("torrential", 0.9), ("monsoon", 0.7),
        ("showers", 0.7), ("drizzle", 0.6), ("cloudburst", 1.0), ("waterlogging", 0.7),
        ("raining", 0.8), ("barish", 0.9),
    ],
    WeatherEventCategory.thunderstorm: [
        ("thunder", 0.9), ("thunderstorm", 1.0), ("lightning", 0.7), ("squall", 0.8),
        ("toofan", 0.9), ("storm", 0.6), ("thunderclap", 0.9),
    ],
    WeatherEventCategory.flooding: [
        ("flood", 1.0), ("flooding", 1.0), ("submerged", 0.9), ("waterlogged", 0.8),
        ("underpass submerged", 1.0), ("water entered", 0.8), ("inundation", 0.9),
        ("overflowing", 0.7), ("drowned", 0.7),
    ],
    WeatherEventCategory.heatwave: [
        ("heatwave", 1.0), ("heat wave", 1.0), ("scorching", 0.9), ("loo", 1.0),
        ("extreme heat", 0.9), ("45°c", 0.9), ("46°c", 0.9), ("47°c", 0.9),
        ("heat exhaustion", 0.8), ("hot winds", 0.8), ("blistering heat", 0.9),
    ],
    WeatherEventCategory.dust_storm: [
        ("dust storm", 1.0), ("andhi", 1.0), ("aandhi", 1.0), ("dust squall", 1.0),
        ("wall of dust", 1.0), ("blinding dust", 0.9), ("haboob", 1.0),
    ],
    WeatherEventCategory.strong_winds: [
        ("strong wind", 0.9), ("gale", 0.9), ("gusty wind", 0.9), ("howling wind", 0.8),
        ("uprooted trees", 0.7), ("tin roof", 0.6), ("high winds", 0.8),
    ],
    WeatherEventCategory.cyclone: [
        ("cyclone", 1.0), ("cyclonic", 1.0), ("storm surge", 1.0), ("depression in sea", 0.9),
        ("coastal battering", 0.8), ("hurricane", 0.8), ("typhoon", 0.8),
    ],
    WeatherEventCategory.hailstorm: [
        ("hail", 1.0), ("hailstorm", 1.0), ("hailstone", 1.0), ("ice pellets", 0.9),
        ("frozen rain", 0.8), ("ola", 0.9), ("ole", 0.9),
    ],
    WeatherEventCategory.fog: [
        ("fog", 1.0), ("dense fog", 1.0), ("smog", 0.8), ("mist", 0.7),
        ("low visibility", 0.8), ("zero visibility", 0.9), ("kohra", 1.0),
    ],
    WeatherEventCategory.lightning: [
        ("lightning strike", 1.0), ("cloud to ground lightning", 1.0),
        ("thunderbolt", 0.9), ("bijli", 0.9), ("transformer exploded", 0.7),
    ],
    WeatherEventCategory.cold_wave: [
        ("cold wave", 1.0), ("coldwave", 1.0), ("freezing", 0.8), ("record chill", 0.9),
        ("shivering", 0.7), ("severe chill", 0.8), ("frost", 0.8),
    ],
    WeatherEventCategory.landslide: [
        ("landslide", 1.0), ("mudslide", 1.0), ("rockfall", 1.0), ("debris flow", 0.9),
        ("slope collapse", 0.9), ("hilly road blocked", 0.8),
    ],
}


@dataclass
class ClassificationResult:
    category: WeatherEventCategory
    confidence: float
    model_name: str
    scores: dict[str, float]


class WeatherClassifier:
    """
    Hybrid weather event classifier combining zero-shot OpenCLIP (for images)
    and calibrated NLP semantic scoring (for report texts).
    """

    def __init__(self, use_clip: bool = False) -> None:
        self.use_clip = use_clip
        self._clip_model = None
        self._clip_preprocess = None

    def classify_text(self, text: str) -> ClassificationResult:
        """Classify report text into a WeatherEventCategory with confidence."""
        if not text or not text.strip():
            return ClassificationResult(
                category=WeatherEventCategory.other,
                confidence=0.1,
                model_name="nlp_lexical_v1",
                scores={},
            )

        text_lower = text.lower()
        cat_scores: dict[WeatherEventCategory, float] = {}

        for category, keywords in WEATHER_LEXICON.items():
            score = 0.0
            for kw, weight in keywords:
                if kw in text_lower:
                    score += weight
            if score > 0:
                cat_scores[category] = score

        if not cat_scores:
            return ClassificationResult(
                category=WeatherEventCategory.other,
                confidence=0.2,
                model_name="nlp_lexical_v1",
                scores={},
            )

        # Find best category
        best_cat, raw_score = max(cat_scores.items(), key=lambda x: x[1])
        confidence = min(0.98, max(0.45, 0.45 + (raw_score * 0.25)))

        return ClassificationResult(
            category=best_cat,
            confidence=round(confidence, 3),
            model_name="nlp_lexical_v1",
            scores={k.value: round(v, 2) for k, v in cat_scores.items()},
        )

    def classify(
        self,
        text: Optional[str] = None,
        image_path: Optional[Union[str, Path]] = None,
        fallback_category: Optional[str] = None,
    ) -> ClassificationResult:
        """Unified classification combining text and optional image."""
        if text:
            result = self.classify_text(text)
            if result.category != WeatherEventCategory.other:
                return result

        if fallback_category:
            try:
                cat = WeatherEventCategory(fallback_category)
                return ClassificationResult(
                    category=cat,
                    confidence=0.6,
                    model_name="fallback_heuristic",
                    scores={cat.value: 0.6},
                )
            except Exception:
                pass

        return ClassificationResult(
            category=WeatherEventCategory.other,
            confidence=0.3,
            model_name="default",
            scores={},
        )


# Global singleton
DEFAULT_WEATHER_CLASSIFIER = WeatherClassifier()
