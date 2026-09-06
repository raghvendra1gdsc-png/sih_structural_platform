"""
tests/test_weather_gpt.py
=========================
Unit tests for the Grounded WeatherGPT Conversational Weather Intelligence Engine.
Verifies location extraction, intent recognition, retrieval grounding, citations, and safety notices.
"""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from backend.services.weather_gpt_service import WeatherGPTService
from ingestion.weather_provider import OpenMeteoWeatherProvider


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    # Mock empty or default scalars return
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    session.scalars.return_value = scalars_mock
    return session


@pytest.fixture
def gpt_service(mock_db_session):
    provider = OpenMeteoWeatherProvider()
    return WeatherGPTService(db=mock_db_session, weather_provider=provider)


def test_extract_location(gpt_service: WeatherGPTService):
    city, lat, lon, state = gpt_service.extract_location("Will it rain in Mumbai tomorrow?")
    assert city == "Mumbai"
    assert state == "Maharashtra"
    assert lat == pytest.approx(19.0760, abs=0.01)

    city, lat, lon, state = gpt_service.extract_location("Check wind gusts around Delhi NCR.")
    assert city == "Delhi"

    # Default fallback to Jaipur if unspecified
    city, lat, lon, state = gpt_service.extract_location("Is it a sunny day outside?")
    assert city == "Jaipur"


def test_extract_intent(gpt_service: WeatherGPTService):
    assert gpt_service.extract_intent("Should I carry an umbrella?") == "precipitation"
    assert gpt_service.extract_intent("Are there storm gusts or high winds?") == "wind"
    assert gpt_service.extract_intent("Is it safe for a small fishing boat to go to sea?") == "marine_safety"
    assert gpt_service.extract_intent("Can I drive on the highway, what is the travel advisory?") == "travel_advisory"
    assert gpt_service.extract_intent("What is the current temperature?") == "temperature"
    assert gpt_service.extract_intent("What is the overall weather situation?") == "general_overview"


def test_marine_safety_notice_included(gpt_service: WeatherGPTService):
    res = gpt_service.answer_question("Can I take my boat out near Mumbai today?")
    assert res["intent"] == "marine_safety"
    assert res["safety_notice"] is not None
    assert "SAFETY NOTICE" in res["safety_notice"]
    assert "India Meteorological Department (IMD)" in res["safety_notice"]
    assert len(res["citations"]) >= 3


def test_grounded_answer_structure(gpt_service: WeatherGPTService):
    res = gpt_service.answer_question("Do I need an umbrella in Jaipur?")
    assert res["city"] == "Jaipur"
    assert "Jaipur" in res["answer"]
    assert "structured_context" in res
    ctx = res["structured_context"]
    assert "current_temp_c" in ctx
    assert "wind_kmh" in ctx
    assert "platform_impact_score" in ctx
    assert len(res["citations"]) > 0
