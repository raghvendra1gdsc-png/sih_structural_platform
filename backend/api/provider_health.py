"""
backend/api/provider_health.py
==============================
REST API endpoints providing live status and operational health telemetry
for all external services:
- Meteorological data providers (Open-Meteo, OpenWeather, Tomorrow.io, WeatherAPI)
- External information sources (GDELT 2.0, Reddit PRAW)
- Large Language Model reasoning engines (Google Gemini, OpenAI GPT)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from backend.llm import GeminiProvider, OpenAIProvider
from ingestion.aggregator import WeatherAggregationService
from ingestion.sources.gdelt import GDELTSource
from ingestion.sources.reddit import RedditSource

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/providers", tags=["providers"])

_aggregator = WeatherAggregationService()
_gdelt = GDELTSource()
_reddit = RedditSource()
_gemini = GeminiProvider()
_openai = OpenAIProvider()


@router.get("/health")
def get_all_provider_health() -> dict[str, Any]:
    """
    Unified health dashboard endpoint for all external API providers,
    sources, and LLM backends.
    """
    weather_health = _aggregator.get_provider_health()
    sources_health = [
        _gdelt.health.to_dict(),
        _reddit.health.to_dict(),
    ]

    llm_health = [
        {
            "provider": _gemini.name,
            "model": _gemini.model,
            "configured": _gemini.is_configured(),
            "status": "ready" if _gemini.is_configured() else "unconfigured",
        },
        {
            "provider": _openai.name,
            "model": _openai.model,
            "configured": _openai.is_configured(),
            "status": "ready" if _openai.is_configured() else "unconfigured",
        },
    ]

    weather_up = sum(1 for p in weather_health if p.get("is_up"))
    weather_total = len(weather_health)

    overall_status = "healthy"
    if weather_up == 0:
        overall_status = "critical"
    elif weather_up < weather_total:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "summary": {
            "weather_providers_up": f"{weather_up}/{weather_total}",
            "primary_weather_provider": "open_meteo",
            "active_llm": "gemini" if _gemini.is_configured() else ("openai" if _openai.is_configured() else "rules_engine"),
        },
        "weather_providers": weather_health,
        "information_sources": sources_health,
        "llm_engines": llm_health,
    }


@router.get("/weather")
def get_weather_provider_health() -> list[dict[str, Any]]:
    """Health telemetry for meteorological APIs."""
    return _aggregator.get_provider_health()


@router.get("/sources")
def get_source_health() -> list[dict[str, Any]]:
    """Health telemetry for news and community feeds."""
    return [
        _gdelt.health.to_dict(),
        _reddit.health.to_dict(),
    ]


@router.get("/llm")
def get_llm_health() -> list[dict[str, Any]]:
    """Configuration and availability of LLM reasoning engines."""
    return [
        {
            "provider": _gemini.name,
            "model": _gemini.model,
            "configured": _gemini.is_configured(),
        },
        {
            "provider": _openai.name,
            "model": _openai.model,
            "configured": _openai.is_configured(),
        },
    ]
