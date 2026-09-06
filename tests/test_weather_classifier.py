"""
tests/test_weather_classifier.py
================================
Unit tests for AI weather event classification (lexical NLP and zero-shot pipeline).
Verifies category mapping, confidence calibration, Indian regional terminology, and edge cases.
"""

from __future__ import annotations

import pytest
from ingestion.weather_schemas import WeatherEventCategory
from ml_pipeline.weather_classifier import WeatherClassifier, DEFAULT_WEATHER_CLASSIFIER


@pytest.fixture
def classifier() -> WeatherClassifier:
    return WeatherClassifier(use_clip=False)


def test_classify_rainfall_and_cloudburst(classifier: WeatherClassifier):
    res = classifier.classify_text("Massive torrential downpour and cloudburst near civil lines.")
    assert res.category == WeatherEventCategory.rainfall
    assert res.confidence >= 0.70
    assert "rainfall" in res.scores


def test_classify_flooding(classifier: WeatherClassifier):
    res = classifier.classify_text("Water entered ground floor shops, underpass completely submerged and flooded.")
    assert res.category == WeatherEventCategory.flooding
    assert res.confidence >= 0.75


def test_classify_heatwave_and_loo(classifier: WeatherClassifier):
    res = classifier.classify_text("Extreme heatwave conditions today, temperature reached 47°C with blistering loo.")
    assert res.category == WeatherEventCategory.heatwave
    assert res.confidence >= 0.80


def test_classify_dust_storm_regional(classifier: WeatherClassifier):
    res = classifier.classify_text("Massive andhi dust storm approaching the highway, blinding dust reducing visibility to zero.")
    assert res.category == WeatherEventCategory.dust_storm
    assert res.confidence >= 0.80


def test_classify_cyclone(classifier: WeatherClassifier):
    res = classifier.classify_text("Deep depression in sea intensifying into severe cyclonic storm with coastal battering.")
    assert res.category == WeatherEventCategory.cyclone
    assert res.confidence >= 0.80


def test_classify_hailstorm(classifier: WeatherClassifier):
    res = classifier.classify_text("Huge hailstones falling and destroying standing crops, ole barish everywhere.")
    assert res.category == WeatherEventCategory.hailstorm
    assert res.confidence >= 0.75


def test_classify_fog_and_smog(classifier: WeatherClassifier):
    res = classifier.classify_text("Dense fog and kohra causing near zero visibility on Eastern Peripheral Expressway.")
    assert res.category == WeatherEventCategory.fog
    assert res.confidence >= 0.75


def test_classify_thunderstorm(classifier: WeatherClassifier):
    res = classifier.classify_text("Violent thunderstorm with deafening thunderclaps and lightning squall.")
    assert res.category in (WeatherEventCategory.thunderstorm, WeatherEventCategory.lightning)
    assert res.confidence >= 0.70


def test_classify_landslide(classifier: WeatherClassifier):
    res = classifier.classify_text("Massive landslide and rockfall blocked the national highway after continuous rains.")
    assert res.category == WeatherEventCategory.landslide
    assert res.confidence >= 0.75


def test_classify_cold_wave(classifier: WeatherClassifier):
    res = classifier.classify_text("Severe cold wave and shivering temperatures recorded across plains.")
    assert res.category == WeatherEventCategory.cold_wave
    assert res.confidence >= 0.70


def test_empty_and_unknown_text(classifier: WeatherClassifier):
    empty_res = classifier.classify_text("")
    assert empty_res.category == WeatherEventCategory.other
    assert empty_res.confidence <= 0.3

    unknown_res = classifier.classify_text("Going to the supermarket to buy groceries.")
    assert unknown_res.category == WeatherEventCategory.other
    assert unknown_res.confidence <= 0.3


def test_fallback_category_heuristic(classifier: WeatherClassifier):
    res = classifier.classify(text="Quiet day", fallback_category="flooding")
    assert res.category == WeatherEventCategory.flooding
    assert res.confidence == 0.6
