"""
tests/test_aggregator.py
========================
Unit tests for WeatherAggregationService:
- Multi-provider consensus agreement calculation
- Temperature spread calculation
- City coordinate resolution
- Unified context generation & caching
- Graceful degradation when all providers fail
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from ingestion.aggregator import (
    WeatherAggregationService,
    _compute_agreement,
    AggregatedWeatherContext,
)
from ingestion.providers.base import NormalizedConditions, NormalizedForecastDay, ProviderResult


class TestAggregatorLogic:
    def test_agreement_single_or_empty(self):
        score, spread = _compute_agreement([])
        assert score == 1.0
        assert spread is None

        score, spread = _compute_agreement([25.0])
        assert score == 1.0
        assert spread is None

    def test_agreement_identical(self):
        score, spread = _compute_agreement([25.0, 25.0, 25.0])
        assert score == 1.0
        assert spread == 0.0

    def test_agreement_moderate_spread(self):
        # max 27, min 25 -> spread 2.0 -> agreement 1.0 - (2/10) = 0.8
        score, spread = _compute_agreement([25.0, 26.0, 27.0])
        assert score == 0.8
        assert spread == 2.0

    def test_agreement_large_spread(self):
        # spread >= 10.0 -> agreement 0.0
        score, spread = _compute_agreement([20.0, 31.0])
        assert score == 0.0
        assert spread == 11.0


class TestWeatherAggregationService:
    def test_city_resolution(self):
        service = WeatherAggregationService()
        lat, lon, state = service.resolve_city("Jaipur")
        assert round(lat, 2) == 26.91
        assert round(lon, 2) == 75.79
        assert state == "Rajasthan"

        # Case insensitive substring
        lat, lon, state = service.resolve_city("South Delhi NCR")
        assert round(lat, 2) == 28.61
        assert state == "Delhi"

        # Unknown city defaults to Jaipur
        lat, lon, state = service.resolve_city("Atlantis")
        assert round(lat, 2) == 26.91

    def test_unified_context_aggregation(self):
        service = WeatherAggregationService()

        # Mock providers
        mock_p1 = MagicMock()
        mock_p1.name = "open_meteo"
        mock_p1.get.return_value = ProviderResult(
            provider_name="open_meteo",
            fetched_at=None,
            is_cached=False,
            current=NormalizedConditions(
                temperature_c=28.0,
                precipitation_mm=0.0,
                wind_kmh=12.0,
                condition_text="Clear",
            ),
            forecast_days=[
                NormalizedForecastDay(
                    date="2026-09-06",
                    temp_max_c=32.0,
                    temp_min_c=24.0,
                    precipitation_prob_pct=20,
                    precipitation_mm=0.0,
                    wind_max_kmh=15.0,
                    condition_text="Sunny",
                )
            ],
        )

        mock_p2 = MagicMock()
        mock_p2.name = "openweather"
        mock_p2.get.return_value = ProviderResult(
            provider_name="openweather",
            fetched_at=None,
            is_cached=False,
            current=NormalizedConditions(
                temperature_c=29.0,
                precipitation_mm=0.0,
                wind_kmh=10.0,
                condition_text="Clear",
            ),
            forecast_days=[],
        )

        service._providers = [mock_p1, mock_p2]

        ctx = service.get_unified_context("Jaipur")
        assert isinstance(ctx, AggregatedWeatherContext)
        assert ctx.city == "Jaipur"
        assert ctx.temperature_c == 28.0  # From primary provider
        assert ctx.tomorrow_temp_max == 32.0
        assert "open_meteo" in ctx.providers_ok
        assert "openweather" in ctx.providers_ok
        assert ctx.agreement_score == 0.9  # Spread is 1.0 C -> 1 - 0.1 = 0.9

        # Verify caching
        ctx_cached = service.get_unified_context("Jaipur")
        assert ctx_cached is ctx
        # Provider should not be called again
        assert mock_p1.get.call_count == 1
