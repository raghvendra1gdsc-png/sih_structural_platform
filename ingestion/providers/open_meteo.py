"""
ingestion/providers/open_meteo.py
==================================
Open-Meteo weather provider adapter.
Free, no API key required. Primary forecast source.
"""
from __future__ import annotations
import logging
from typing import Any
import requests
from ingestion.providers.base import (
    NormalizedConditions, NormalizedForecastDay, WeatherProvider
)

logger = logging.getLogger(__name__)
BASE_URL = "https://api.open-meteo.com/v1/forecast"

WMO_CODES = {
    0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
    45:"Fog",48:"Rime fog",51:"Light drizzle",53:"Moderate drizzle",55:"Dense drizzle",
    61:"Slight rain",63:"Moderate rain",65:"Heavy rain",
    71:"Slight snow",73:"Moderate snow",75:"Heavy snow",77:"Snow grains",
    80:"Slight showers",81:"Moderate showers",82:"Violent showers",
    95:"Thunderstorm",96:"Thunderstorm+hail",99:"Thunderstorm+heavy hail",
}


class OpenMeteoProvider(WeatherProvider):
    @property
    def name(self) -> str:
        return "open_meteo"

    def _fetch_current(self, lat: float, lon: float) -> NormalizedConditions:
        params: dict[str, Any] = {
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "timezone": "Asia/Kolkata",
        }
        resp = requests.get(BASE_URL, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        c = data.get("current", {})
        code = c.get("weather_code", 0)
        return NormalizedConditions(
            temperature_c=c.get("temperature_2m", 28.0),
            apparent_temperature_c=c.get("apparent_temperature"),
            humidity_pct=c.get("relative_humidity_2m"),
            precipitation_mm=c.get("precipitation", 0.0),
            wind_kmh=c.get("wind_speed_10m", 0.0),
            wind_gust_kmh=c.get("wind_gusts_10m"),
            wind_direction_deg=c.get("wind_direction_10m"),
            weather_code=code,
            condition_text=WMO_CODES.get(code, "Cloudy/Unsettled"),
        )

    def _fetch_forecast(self, lat: float, lon: float) -> list[NormalizedForecastDay]:
        params: dict[str, Any] = {
            "latitude": lat, "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max",
            "timezone": "Asia/Kolkata",
        }
        resp = requests.get(BASE_URL, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        daily = data.get("daily", {})
        times = daily.get("time", [])
        return [
            NormalizedForecastDay(
                date=times[i],
                temp_max_c=daily.get("temperature_2m_max", [])[i] if i < len(daily.get("temperature_2m_max",[])) else 30.0,
                temp_min_c=daily.get("temperature_2m_min", [])[i] if i < len(daily.get("temperature_2m_min",[])) else 22.0,
                precipitation_mm=daily.get("precipitation_sum", [])[i] if i < len(daily.get("precipitation_sum",[])) else 0.0,
                precipitation_prob_pct=int(daily.get("precipitation_probability_max", [])[i] or 0) if i < len(daily.get("precipitation_probability_max",[])) else 0,
                wind_max_kmh=daily.get("wind_speed_10m_max", [])[i] if i < len(daily.get("wind_speed_10m_max",[])) else 0.0,
                wind_gust_max_kmh=daily.get("wind_gusts_10m_max", [])[i] if i < len(daily.get("wind_gusts_10m_max",[])) else None,
                weather_code=daily.get("weather_code", [])[i] if i < len(daily.get("weather_code",[])) else None,
                condition_text=WMO_CODES.get(daily.get("weather_code", [])[i] if i < len(daily.get("weather_code",[])) else 0, "Unknown"),
            )
            for i in range(len(times))
        ]
