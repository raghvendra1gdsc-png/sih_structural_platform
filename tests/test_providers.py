"""
tests/test_providers.py
=======================
Unit and integration tests for meteorological data providers:
- Open-Meteo
- OpenWeather
- Tomorrow.io
- WeatherAPI
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from ingestion.providers.base import NormalizedConditions, NormalizedForecastDay, ProviderResult
from ingestion.providers.open_meteo import OpenMeteoProvider
from ingestion.providers.openweather import OpenWeatherProvider
from ingestion.providers.tomorrow import TomorrowProvider
from ingestion.providers.weatherapi import WeatherAPIProvider


class TestOpenMeteoProvider:
    def test_initialization(self):
        provider = OpenMeteoProvider()
        assert provider.name == "open_meteo"
        assert provider.is_configured() is True

    @patch("requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "current": {
                "temperature_2m": 28.5,
                "apparent_temperature": 30.1,
                "precipitation": 0.5,
                "relative_humidity_2m": 65,
                "surface_pressure": 1012.0,
                "wind_speed_10m": 14.2,
                "wind_gusts_10m": 22.0,
                "weather_code": 61,
            },
            "daily": {
                "time": ["2026-09-05", "2026-09-06"],
                "temperature_2m_max": [32.0, 31.0],
                "temperature_2m_min": [24.0, 23.5],
                "precipitation_sum": [2.5, 0.0],
                "precipitation_probability_max": [80, 20],
                "wind_speed_10m_max": [20.0, 15.0],
                "weather_code": [61, 1],
            },
        }
        mock_get.return_value = mock_resp

        provider = OpenMeteoProvider()
        result = provider.get(26.91, 75.79, use_cache=False)
        assert result.ok
        assert result.current is not None
        assert result.current.temperature_c == 28.5
        assert result.current.precipitation_mm == 0.5
        assert len(result.forecast_days) == 2
        assert result.forecast_days[0].precipitation_prob_pct == 80


class TestOpenWeatherProvider:
    def test_not_configured_without_key(self):
        provider = OpenWeatherProvider()
        provider._key = ""
        assert not provider.is_configured()
        res = provider.get(26.91, 75.79, use_cache=False)
        assert not res.ok
        assert "OPENWEATHER_API_KEY not configured" in (res.error or "")

    @patch("requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "main": {"temp": 26.5, "feels_like": 28.0, "humidity": 70, "pressure": 1010},
            "wind": {"speed": 4.5, "gust": 7.2},  # m/s -> km/h
            "weather": [{"main": "Rain", "description": "light rain", "id": 500}],
            "rain": {"1h": 1.2},
        }
        mock_get.return_value = mock_resp

        provider = OpenWeatherProvider()
        provider._key = "dummy_key"
        res = provider.get(26.91, 75.79, use_cache=False)
        assert res.ok
        assert res.current.temperature_c == 26.5
        assert round(res.current.wind_kmh, 1) == 16.2  # 4.5 * 3.6
        assert res.current.precipitation_mm == 1.2


class TestTomorrowIOProvider:
    def test_not_configured_without_key(self):
        provider = TomorrowProvider()
        provider._key = ""
        assert not provider.is_configured()
        res = provider.get(26.91, 75.79, use_cache=False)
        assert not res.ok

    @patch("requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "values": {
                    "temperature": 27.0,
                    "temperatureApparent": 29.5,
                    "precipitationIntensity": 0.2,
                    "windSpeed": 5.0,  # m/s -> km/h
                    "windGust": 8.0,
                    "humidity": 60,
                    "pressureSurfaceLevel": 1012,
                    "weatherCode": 1000,
                }
            }
        }
        mock_get.return_value = mock_resp

        provider = TomorrowProvider()
        provider._key = "dummy_key"
        res = provider.get(26.91, 75.79, use_cache=False)
        assert res.ok
        assert res.current.temperature_c == 27.0
        assert round(res.current.wind_kmh, 1) == 18.0


class TestWeatherAPIProvider:
    def test_not_configured_without_key(self):
        provider = WeatherAPIProvider()
        provider._key = ""
        assert not provider.is_configured()
        res = provider.get(26.91, 75.79, use_cache=False)
        assert not res.ok

    @patch("requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "current": {
                "temp_c": 25.0,
                "feelslike_c": 26.5,
                "precip_mm": 0.0,
                "wind_kph": 12.0,
                "wind_gust_kph": 18.0,
                "humidity": 55,
                "pressure_mb": 1014.0,
                "uv": 5.0,
                "condition": {"text": "Partly cloudy", "code": 1003},
            },
            "forecast": {
                "forecastday": [
                    {
                        "date": "2026-09-05",
                        "day": {
                            "maxtemp_c": 31.0,
                            "mintemp_c": 23.0,
                            "totalprecip_mm": 0.5,
                            "daily_chance_of_rain": 30,
                            "maxwind_kph": 15.0,
                            "uv": 6.0,
                            "condition": {"text": "Patchy rain possible"},
                        },
                    }
                ]
            },
        }
        mock_get.return_value = mock_resp

        provider = WeatherAPIProvider()
        provider._key = "dummy_key"
        res = provider.get(26.91, 75.79, use_cache=False)
        assert res.ok
        assert res.current.temperature_c == 25.0
        assert len(res.forecast_days) == 1
        assert res.forecast_days[0].uv_index == 6.0
