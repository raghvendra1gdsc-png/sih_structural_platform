"""
ingestion/weather_provider.py
=============================
Abstract Weather Provider interface and Open-Meteo client.
Supports current conditions, hourly and daily forecasts, with robust local caching
and graceful fallback for 100% offline demonstration reliability.
"""

from __future__ import annotations

import abc
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests

from ingestion.weather_schemas import OpenMeteoResponse

logger = logging.getLogger(__name__)

# Cache directory and default offline sample
CACHE_DIR = Path("data/sample_dataset")
DEFAULT_CACHE_FILE = CACHE_DIR / "weather_cache.json"

# Key Indian Cities Coordinates for quick lookup & caching
INDIAN_CITIES: dict[str, dict[str, Any]] = {
    "Jaipur": {"lat": 26.9124, "lon": 75.7873, "state": "Rajasthan"},
    "Jodhpur": {"lat": 26.2389, "lon": 73.0243, "state": "Rajasthan"},
    "Delhi": {"lat": 28.6139, "lon": 77.2090, "state": "Delhi"},
    "Mumbai": {"lat": 19.0760, "lon": 72.8777, "state": "Maharashtra"},
    "Chennai": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu"},
    "Kolkata": {"lat": 22.5726, "lon": 88.3639, "state": "West Bengal"},
    "Bengaluru": {"lat": 12.9716, "lon": 77.5946, "state": "Karnataka"},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867, "state": "Telangana"},
    "Guwahati": {"lat": 26.1445, "lon": 91.7362, "state": "Assam"},
    "Ahmedabad": {"lat": 23.0225, "lon": 72.5714, "state": "Gujarat"},
    "Lucknow": {"lat": 26.8467, "lon": 80.9462, "state": "Uttar Pradesh"},
    "Kochi": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala"},
}


class WeatherProvider(abc.ABC):
    """Abstract interface for weather providers."""

    @abc.abstractmethod
    def get_forecast(
        self,
        latitude: float,
        longitude: float,
        hourly: bool = True,
        daily: bool = True,
    ) -> OpenMeteoResponse:
        """Fetch forecast data for coordinates."""
        pass

    @abc.abstractmethod
    def get_current_conditions(
        self,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        """Fetch current weather metrics."""
        pass


class OpenMeteoWeatherProvider(WeatherProvider):
    """
    Production-style provider wrapping Open-Meteo's free, no-key public API.
    Includes in-memory TTL caching and disk persistence for offline demo fallback.
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(
        self,
        timeout_seconds: float = 8.0,
        cache_ttl_seconds: int = 1800,  # 30 minutes
        cache_file: Path = DEFAULT_CACHE_FILE,
        offline_mode: bool = False,
    ) -> None:
        self.timeout = timeout_seconds
        self.cache_ttl = cache_ttl_seconds
        self.cache_file = cache_file
        self.offline_mode = offline_mode
        self._memory_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._disk_cache: dict[str, dict[str, Any]] = self._load_disk_cache()

    def _cache_key(self, lat: float, lon: float) -> str:
        return f"{round(lat, 2)}_{round(lon, 2)}"

    def _load_disk_cache(self) -> dict[str, dict[str, Any]]:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Could not read weather disk cache: %s", e)
        return {}

    def _save_disk_cache(self) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._disk_cache, f, indent=2)
        except Exception as e:
            logger.warning("Could not persist weather disk cache: %s", e)

    def get_forecast(
        self,
        latitude: float,
        longitude: float,
        hourly: bool = True,
        daily: bool = True,
    ) -> OpenMeteoResponse:
        key = self._cache_key(latitude, longitude)
        now = time.time()

        # Check in-memory cache
        if key in self._memory_cache:
            ts, data = self._memory_cache[key]
            if now - ts < self.cache_ttl:
                return OpenMeteoResponse.model_validate(data)

        # Check offline mode
        if self.offline_mode:
            if key in self._disk_cache:
                return OpenMeteoResponse.model_validate(self._disk_cache[key])
            return self._build_synthetic_forecast(latitude, longitude)

        # Fetch from remote Open-Meteo
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "timezone": "Asia/Kolkata",
        }
        if hourly:
            params["hourly"] = "temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m"
        if daily:
            params["daily"] = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max"

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            # Store in caches
            self._memory_cache[key] = (now, data)
            self._disk_cache[key] = data
            self._save_disk_cache()
            return OpenMeteoResponse.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to fetch live weather for (%s, %s): %s. Falling back to cache/synthetic.", latitude, longitude, exc)
            if key in self._disk_cache:
                return OpenMeteoResponse.model_validate(self._disk_cache[key])
            # Return plausible fallback
            fallback = self._build_synthetic_forecast(latitude, longitude)
            return fallback

    def get_current_conditions(
        self,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        forecast = self.get_forecast(latitude, longitude, hourly=False, daily=False)
        curr = forecast.current
        if not curr:
            return {
                "temperature_c": 28.0,
                "apparent_temperature_c": 31.0,
                "humidity": 65,
                "precipitation_mm": 0.0,
                "wind_kmh": 14.0,
                "wind_gust_kmh": 22.0,
                "wind_direction_deg": 180,
                "weather_code": 1,
                "condition": "Mainly Clear",
            }
        return {
            "temperature_c": curr.temperature_2m or 27.0,
            "apparent_temperature_c": curr.apparent_temperature or 29.0,
            "humidity": curr.relative_humidity_2m or 60,
            "precipitation_mm": curr.precipitation or 0.0,
            "wind_kmh": curr.wind_speed_10m or 12.0,
            "wind_gust_kmh": curr.wind_gusts_10m or 18.0,
            "wind_direction_deg": curr.wind_direction_10m or 90,
            "weather_code": curr.weather_code or 0,
            "condition": self._wmo_code_to_text(curr.weather_code or 0),
        }

    def _build_synthetic_forecast(self, latitude: float, longitude: float) -> OpenMeteoResponse:
        """Deterministic plausible fallback forecast."""
        return OpenMeteoResponse(
            latitude=latitude,
            longitude=longitude,
            timezone="Asia/Kolkata",
            current={
                "time": "2026-09-04T12:00",
                "temperature_2m": 31.5,
                "relative_humidity_2m": 72.0,
                "apparent_temperature": 36.2,
                "precipitation": 12.4,
                "rain": 12.4,
                "weather_code": 95,  # Thunderstorm
                "wind_speed_10m": 24.5,
                "wind_direction_10m": 210.0,
                "wind_gusts_10m": 42.0,
            },
            hourly={
                "time": [f"2026-09-04T{h:02d}:00" for h in range(24)],
                "temperature_2m": [26.0 + (h % 8) for h in range(24)],
                "precipitation_probability": [20, 30, 45, 60, 85, 90, 75, 50] * 3,
                "precipitation": [0.0, 0.0, 1.2, 4.5, 12.4, 8.2, 3.1, 0.5] * 3,
                "weather_code": [95 if (h >= 12 and h <= 18) else 61 for h in range(24)],
                "wind_speed_10m": [15.0 + (h % 10) for h in range(24)],
                "wind_gusts_10m": [25.0 + (h % 15) for h in range(24)],
            },
            daily={
                "time": ["2026-09-04", "2026-09-05", "2026-09-06", "2026-09-07", "2026-09-08"],
                "weather_code": [95, 63, 61, 80, 2],
                "temperature_2m_max": [33.0, 32.0, 31.5, 30.0, 32.5],
                "temperature_2m_min": [24.0, 23.5, 23.0, 22.0, 23.0],
                "precipitation_sum": [35.2, 18.4, 8.2, 4.0, 0.0],
                "precipitation_probability_max": [90, 75, 60, 40, 15],
                "wind_speed_10m_max": [38.0, 30.0, 22.0, 18.0, 15.0],
                "wind_gusts_10m_max": [55.0, 44.0, 32.0, 26.0, 20.0],
            },
        )

    @staticmethod
    def _wmo_code_to_text(code: int) -> str:
        """Convert WMO weather code to human-readable description."""
        mapping = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return mapping.get(code, "Cloudy / Unsettled")
