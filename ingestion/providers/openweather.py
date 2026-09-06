"""
ingestion/providers/openweather.py
====================================
OpenWeatherMap provider adapter (secondary, cross-validation).
Uses Current Weather API v2.5 + 5-day forecast.
Key read from environment — never hardcoded.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime
from typing import Any
import requests
from ingestion.providers.base import (
    NormalizedConditions, NormalizedForecastDay, WeatherProvider
)

logger = logging.getLogger(__name__)

CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


class OpenWeatherProvider(WeatherProvider):
    def __init__(self) -> None:
        super().__init__(cache_ttl_seconds=1800)
        from backend.core.config import settings
        self._key = settings.OPENWEATHER_API_KEY
        if not self._key:
            logger.warning("[openweather] OPENWEATHER_API_KEY not set — provider disabled")

    @property
    def name(self) -> str:
        return "openweather"

    def is_configured(self) -> bool:
        return bool(self._key)

    def _fetch_current(self, lat: float, lon: float) -> NormalizedConditions:

        if not self._key:
            raise RuntimeError("OPENWEATHER_API_KEY not configured")
        resp = requests.get(
            CURRENT_URL,
            params={"lat": lat, "lon": lon, "appid": self._key, "units": "metric"},
            timeout=8,
        )
        resp.raise_for_status()
        d = resp.json()
        main = d.get("main", {})
        wind = d.get("wind", {})
        weather_list = d.get("weather", [{}])
        rain = d.get("rain", {})
        return NormalizedConditions(
            temperature_c=main.get("temp", 28.0),
            apparent_temperature_c=main.get("feels_like"),
            humidity_pct=main.get("humidity"),
            precipitation_mm=rain.get("1h", 0.0),
            wind_kmh=round((wind.get("speed", 0.0)) * 3.6, 1),  # m/s → km/h
            wind_gust_kmh=round((wind.get("gust", 0.0)) * 3.6, 1) if wind.get("gust") else None,
            wind_direction_deg=wind.get("deg"),
            condition_text=weather_list[0].get("description", "Unknown").title(),
            visibility_km=round(d.get("visibility", 10000) / 1000, 1),
            pressure_hpa=main.get("pressure"),
        )

    def _fetch_forecast(self, lat: float, lon: float) -> list[NormalizedForecastDay]:
        if not self._key:
            raise RuntimeError("OPENWEATHER_API_KEY not configured")
        resp = requests.get(
            FORECAST_URL,
            params={"lat": lat, "lon": lon, "appid": self._key, "units": "metric", "cnt": 40},
            timeout=10,
        )
        resp.raise_for_status()
        d = resp.json()
        # Group 3h slots by day
        day_map: dict[str, dict[str, Any]] = {}
        for item in d.get("list", []):
            dt = datetime.utcfromtimestamp(item["dt"])
            day = dt.strftime("%Y-%m-%d")
            if day not in day_map:
                day_map[day] = {"temps": [], "precip": 0.0, "winds": [], "desc": ""}
            day_map[day]["temps"].append(item["main"]["temp"])
            day_map[day]["precip"] += item.get("rain", {}).get("3h", 0.0)
            day_map[day]["winds"].append(item["wind"].get("speed", 0.0) * 3.6)
            day_map[day]["desc"] = item["weather"][0]["description"].title()
        result = []
        for day, data in sorted(day_map.items())[:7]:
            temps = data["temps"]
            result.append(NormalizedForecastDay(
                date=day,
                temp_max_c=max(temps),
                temp_min_c=min(temps),
                precipitation_mm=round(data["precip"], 1),
                wind_max_kmh=round(max(data["winds"]), 1),
                condition_text=data["desc"],
            ))
        return result
