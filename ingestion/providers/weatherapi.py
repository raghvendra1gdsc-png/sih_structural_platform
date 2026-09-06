"""
ingestion/providers/weatherapi.py
===================================
WeatherAPI.com provider adapter (quaternary, cross-validation).
Uses Current + Forecast JSON API v1.
Key read from environment — never hardcoded.
"""
from __future__ import annotations
import logging
import requests
from ingestion.providers.base import (
    NormalizedConditions, NormalizedForecastDay, WeatherProvider
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.weatherapi.com/v1"


class WeatherAPIProvider(WeatherProvider):
    def __init__(self) -> None:
        super().__init__(cache_ttl_seconds=1800)
        from backend.core.config import settings
        self._key = settings.WEATHERAPI_KEY
        if not self._key:
            logger.warning("[weatherapi] WEATHERAPI_KEY not set — provider disabled")

    @property
    def name(self) -> str:
        return "weatherapi"

    def is_configured(self) -> bool:
        return bool(self._key)

    def _fetch_current(self, lat: float, lon: float) -> NormalizedConditions:

        if not self._key:
            raise RuntimeError("WEATHERAPI_KEY not configured")
        resp = requests.get(
            f"{BASE_URL}/current.json",
            params={"key": self._key, "q": f"{lat},{lon}", "aqi": "no"},
            timeout=8,
        )
        resp.raise_for_status()
        d = resp.json()
        c = d.get("current", {})
        cond = c.get("condition", {})
        return NormalizedConditions(
            temperature_c=c.get("temp_c", 28.0),
            apparent_temperature_c=c.get("feelslike_c"),
            humidity_pct=c.get("humidity"),
            precipitation_mm=c.get("precip_mm", 0.0),
            wind_kmh=c.get("wind_kph", 0.0),
            wind_gust_kmh=c.get("gust_kph"),
            wind_direction_deg=c.get("wind_degree"),
            condition_text=cond.get("text", "Unknown"),
            visibility_km=c.get("vis_km"),
            pressure_hpa=c.get("pressure_mb"),
            uv_index=c.get("uv"),
        )

    def _fetch_forecast(self, lat: float, lon: float) -> list[NormalizedForecastDay]:
        if not self._key:
            raise RuntimeError("WEATHERAPI_KEY not configured")
        resp = requests.get(
            f"{BASE_URL}/forecast.json",
            params={"key": self._key, "q": f"{lat},{lon}", "days": 7, "aqi": "no", "alerts": "no"},
            timeout=10,
        )
        resp.raise_for_status()
        d = resp.json()
        days = d.get("forecast", {}).get("forecastday", [])
        result = []
        for day in days:
            dday = day.get("day", {})
            cond = dday.get("condition", {})
            result.append(NormalizedForecastDay(
                date=day.get("date", ""),
                temp_max_c=dday.get("maxtemp_c", 30.0),
                temp_min_c=dday.get("mintemp_c", 22.0),
                precipitation_mm=dday.get("totalprecip_mm", 0.0),
                precipitation_prob_pct=int(dday.get("daily_chance_of_rain", 0)),
                wind_max_kmh=dday.get("maxwind_kph", 0.0),
                uv_index=dday.get("uv"),
                condition_text=cond.get("text", "Unknown"),
            ))
        return result
