"""
ingestion/providers/tomorrow.py
=================================
Tomorrow.io provider adapter (tertiary, nowcasting).
Uses Realtime + Timelines v4 API.
Key read from environment — never hardcoded.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
import requests
from ingestion.providers.base import (
    NormalizedConditions, NormalizedForecastDay, WeatherProvider
)

logger = logging.getLogger(__name__)

REALTIME_URL = "https://api.tomorrow.io/v4/weather/realtime"
FORECAST_URL = "https://api.tomorrow.io/v4/weather/forecast"

# Tomorrow.io weatherCode → text mapping (subset)
TOMORROW_CODES: dict[int, str] = {
    1000:"Clear",1100:"Mostly Clear",1101:"Partly Cloudy",1102:"Mostly Cloudy",
    1001:"Cloudy",2000:"Fog",2100:"Light Fog",4000:"Drizzle",4001:"Rain",
    4200:"Light Rain",4201:"Heavy Rain",5000:"Snow",5001:"Flurries",
    5100:"Light Snow",5101:"Heavy Snow",6000:"Freezing Drizzle",
    7000:"Ice Pellets",8000:"Thunderstorm",
}


class TomorrowProvider(WeatherProvider):
    def __init__(self) -> None:
        super().__init__(cache_ttl_seconds=900)  # 15-min cache (nowcast)
        from backend.core.config import settings
        self._key = settings.TOMORROW_IO_API_KEY
        if not self._key:
            logger.warning("[tomorrow] TOMORROW_IO_API_KEY not set — provider disabled")

    @property
    def name(self) -> str:
        return "tomorrow_io"

    def is_configured(self) -> bool:
        return bool(self._key)

    def _fetch_current(self, lat: float, lon: float) -> NormalizedConditions:

        if not self._key:
            raise RuntimeError("TOMORROW_IO_API_KEY not configured")
        resp = requests.get(
            REALTIME_URL,
            params={
                "location": f"{lat},{lon}",
                "apikey": self._key,
                "units": "metric",
            },
            timeout=10,
        )
        resp.raise_for_status()
        d = resp.json()
        v = d.get("data", {}).get("values", {})
        code = v.get("weatherCode", 1000)
        return NormalizedConditions(
            temperature_c=v.get("temperature", 28.0),
            apparent_temperature_c=v.get("temperatureApparent"),
            humidity_pct=int(v.get("humidity", 60)),
            precipitation_mm=v.get("precipitationIntensity", 0.0),
            wind_kmh=round(v.get("windSpeed", 0.0) * 3.6, 1),  # m/s → km/h
            wind_gust_kmh=round(v.get("windGust", 0.0) * 3.6, 1) if v.get("windGust") else None,
            wind_direction_deg=int(v.get("windDirection", 0)),
            weather_code=code,
            condition_text=TOMORROW_CODES.get(code, "Unknown"),
            visibility_km=v.get("visibility"),
            pressure_hpa=v.get("pressureSurfaceLevel"),
            uv_index=v.get("uvIndex"),
        )

    def _fetch_forecast(self, lat: float, lon: float) -> list[NormalizedForecastDay]:
        if not self._key:
            raise RuntimeError("TOMORROW_IO_API_KEY not configured")
        resp = requests.get(
            FORECAST_URL,
            params={
                "location": f"{lat},{lon}",
                "apikey": self._key,
                "units": "metric",
            },
            timeout=12,
        )
        resp.raise_for_status()
        d = resp.json()
        days = d.get("timelines", {}).get("daily", [])
        result = []
        for day in days[:7]:
            v = day.get("values", {})
            dt_str = day.get("time", "")[:10]
            code = v.get("weatherCodeMax", 1000)
            result.append(NormalizedForecastDay(
                date=dt_str,
                temp_max_c=v.get("temperatureMax", 30.0),
                temp_min_c=v.get("temperatureMin", 22.0),
                precipitation_mm=round(v.get("precipitationIntensityAvg", 0.0) * 24, 1),
                precipitation_prob_pct=int(v.get("precipitationProbabilityAvg", 0) * 100),
                wind_max_kmh=round(v.get("windSpeedMax", 0.0) * 3.6, 1),
                wind_gust_max_kmh=round(v.get("windGustMax", 0.0) * 3.6, 1) if v.get("windGustMax") else None,
                weather_code=code,
                condition_text=TOMORROW_CODES.get(code, "Unknown"),
            ))
        return result
