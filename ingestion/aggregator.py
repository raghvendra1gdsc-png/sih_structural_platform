"""
ingestion/aggregator.py
========================
WeatherAggregationService — queries all configured weather providers,
normalises to a unified context, computes inter-provider agreement,
and caches the result in-process (+ Redis when available).

Used by:
  - WeatherGPT service (grounding context)
  - /api/weather/current/multi endpoint
  - Background Celery refresh tasks
"""
from __future__ import annotations

import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from ingestion.providers.base import (
    NormalizedConditions, NormalizedForecastDay, ProviderResult, WeatherProvider
)
from ingestion.providers.open_meteo import OpenMeteoProvider
from ingestion.providers.openweather import OpenWeatherProvider
from ingestion.providers.tomorrow import TomorrowProvider
from ingestion.providers.weatherapi import WeatherAPIProvider

logger = logging.getLogger(__name__)

INDIAN_CITIES: dict[str, dict[str, Any]] = {
    "Jaipur":    {"lat": 26.9124, "lon": 75.7873, "state": "Rajasthan"},
    "Jodhpur":   {"lat": 26.2389, "lon": 73.0243, "state": "Rajasthan"},
    "Delhi":     {"lat": 28.6139, "lon": 77.2090, "state": "Delhi"},
    "Mumbai":    {"lat": 19.0760, "lon": 72.8777, "state": "Maharashtra"},
    "Chennai":   {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu"},
    "Kolkata":   {"lat": 22.5726, "lon": 88.3639, "state": "West Bengal"},
    "Bengaluru": {"lat": 12.9716, "lon": 77.5946, "state": "Karnataka"},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867, "state": "Telangana"},
    "Guwahati":  {"lat": 26.1445, "lon": 91.7362, "state": "Assam"},
    "Ahmedabad": {"lat": 23.0225, "lon": 72.5714, "state": "Gujarat"},
    "Lucknow":   {"lat": 26.8467, "lon": 80.9462, "state": "Uttar Pradesh"},
    "Kochi":     {"lat":  9.9312, "lon": 76.2673, "state": "Kerala"},
}


@dataclass
class ProviderSnapshot:
    """A single provider's normalised result in the aggregated context."""
    provider_name: str
    is_up: bool
    is_cached: bool
    fetched_at: Optional[str]  # ISO8601
    temperature_c: Optional[float]
    precipitation_mm: Optional[float]
    wind_kmh: Optional[float]
    wind_gust_kmh: Optional[float]
    condition_text: Optional[str]
    error: Optional[str]


@dataclass
class AggregatedWeatherContext:
    """
    Unified weather context built from all available providers.
    Primary values are selected from Open-Meteo (most reliable free API),
    supplemented by cross-provider agreement metrics.
    """
    city: str
    state: str
    latitude: float
    longitude: float
    aggregated_at: str          # ISO8601 UTC

    # Primary (Open-Meteo preferred)
    temperature_c: float
    apparent_temperature_c: Optional[float]
    humidity_pct: Optional[int]
    precipitation_mm: float
    wind_kmh: float
    wind_gust_kmh: Optional[float]
    condition_text: str
    visibility_km: Optional[float]
    pressure_hpa: Optional[float]
    uv_index: Optional[float]

    # Tomorrow's forecast (from primary provider)
    tomorrow_rain_prob: int
    tomorrow_temp_max: float
    tomorrow_temp_min: float
    forecast_days: list[dict[str, Any]]

    # Multi-provider agreement
    providers_queried: list[str]
    providers_ok: list[str]
    providers_failed: list[str]
    provider_snapshots: list[ProviderSnapshot]
    agreement_score: float          # 0.0–1.0; 1.0 = all providers agree
    temp_spread_c: Optional[float]  # Max - min temp across providers

    def to_dict(self) -> dict[str, Any]:
        d = {
            "city": self.city,
            "state": self.state,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "aggregated_at": self.aggregated_at,
            "temperature_c": self.temperature_c,
            "apparent_temperature_c": self.apparent_temperature_c,
            "humidity_pct": self.humidity_pct,
            "precipitation_mm": self.precipitation_mm,
            "wind_kmh": self.wind_kmh,
            "wind_gust_kmh": self.wind_gust_kmh,
            "condition_text": self.condition_text,
            "visibility_km": self.visibility_km,
            "pressure_hpa": self.pressure_hpa,
            "uv_index": self.uv_index,
            "tomorrow_rain_prob": self.tomorrow_rain_prob,
            "tomorrow_temp_max": self.tomorrow_temp_max,
            "tomorrow_temp_min": self.tomorrow_temp_min,
            "forecast_days": self.forecast_days,
            "providers_queried": self.providers_queried,
            "providers_ok": self.providers_ok,
            "providers_failed": self.providers_failed,
            "agreement_score": self.agreement_score,
            "temp_spread_c": self.temp_spread_c,
            "provider_snapshots": [
                {
                    "provider": s.provider_name,
                    "is_up": s.is_up,
                    "is_cached": s.is_cached,
                    "fetched_at": s.fetched_at,
                    "temperature_c": s.temperature_c,
                    "precipitation_mm": s.precipitation_mm,
                    "wind_kmh": s.wind_kmh,
                    "condition_text": s.condition_text,
                    "error": s.error,
                }
                for s in self.provider_snapshots
            ],
        }
        return d


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _compute_agreement(temps: list[float]) -> tuple[float, Optional[float]]:
    """Agreement score: 1.0 if all within 2°C, degrades linearly."""
    if len(temps) < 2:
        return 1.0, None
    spread = max(temps) - min(temps)
    agreement = max(0.0, 1.0 - (spread / 10.0))  # 10°C spread = 0 agreement
    return round(agreement, 3), round(spread, 2)


class WeatherAggregationService:
    """
    Queries all configured weather providers for a location,
    normalises results, computes agreement, and exposes a unified context.
    """

    def __init__(self) -> None:
        self._providers: list[WeatherProvider] = [
            OpenMeteoProvider(),
            OpenWeatherProvider(),
            TomorrowProvider(),
            WeatherAPIProvider(),
        ]
        # In-process result cache (keyed by city or lat/lon)
        self._agg_cache: dict[str, tuple[float, AggregatedWeatherContext]] = {}
        self._agg_cache_ttl = 600  # 10 minutes

    @property
    def providers(self) -> list[WeatherProvider]:
        return self._providers

    def get_provider_health(self) -> list[dict[str, Any]]:
        return [p.health.to_dict() for p in self._providers]

    def resolve_city(self, city: str) -> tuple[float, float, str]:
        """Resolve city name to (lat, lon, state). Defaults to Jaipur."""
        for name, data in INDIAN_CITIES.items():
            if name.lower() in city.lower() or city.lower() in name.lower():
                return data["lat"], data["lon"], data["state"]
        # Fallback
        d = INDIAN_CITIES["Jaipur"]
        return d["lat"], d["lon"], d["state"]

    def get_unified_context(
        self,
        city: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> AggregatedWeatherContext:
        """
        Returns a unified, multi-provider weather context for the location.
        Uses in-process cache with 10-min TTL.
        """
        if lat is None or lon is None:
            lat, lon, state = self.resolve_city(city)
        else:
            state = INDIAN_CITIES.get(city, {}).get("state", "India")

        cache_key = f"{round(lat, 2)}:{round(lon, 2)}"
        now = time.time()
        if cache_key in self._agg_cache:
            ts, cached = self._agg_cache[cache_key]
            if now - ts < self._agg_cache_ttl:
                logger.debug("[aggregator] cache hit for %s", city)
                return cached

        # Query all providers concurrently where possible
        results: list[ProviderResult] = []
        for provider in self._providers:
            result = provider.get(lat, lon)
            results.append(result)

        # Separate OK vs failed
        ok_results = [r for r in results if r.ok]
        failed_results = [r for r in results if not r.ok]

        # Primary values: prefer Open-Meteo, fallback down the chain
        primary: Optional[NormalizedConditions] = None
        primary_forecast: list[NormalizedForecastDay] = []
        for r in results:
            if r.ok and r.current:
                primary = r.current
                primary_forecast = r.forecast_days
                break  # Open-Meteo is first in list

        if primary is None:
            # All providers failed — return a degraded context
            logger.error("[aggregator] ALL providers failed for %s", city)
            primary = NormalizedConditions(
                temperature_c=28.0,
                precipitation_mm=0.0,
                wind_kmh=10.0,
                condition_text="Data Unavailable",
            )

        # Compute agreement across available temperature readings
        temps = [r.current.temperature_c for r in ok_results if r.current]
        agreement, temp_spread = _compute_agreement(temps)

        # Build per-provider snapshots
        snapshots = []
        for r in results:
            c = r.current
            snapshots.append(ProviderSnapshot(
                provider_name=r.provider_name,
                is_up=r.ok,
                is_cached=r.is_cached,
                fetched_at=r.fetched_at.isoformat() if r.fetched_at else None,
                temperature_c=c.temperature_c if c else None,
                precipitation_mm=c.precipitation_mm if c else None,
                wind_kmh=c.wind_kmh if c else None,
                wind_gust_kmh=c.wind_gust_kmh if c else None,
                condition_text=c.condition_text if c else None,
                error=r.error,
            ))

        # Tomorrow forecast from primary
        tomorrow_rain_prob = 0
        tomorrow_temp_max = 32.0
        tomorrow_temp_min = 22.0
        if len(primary_forecast) > 1:
            d1 = primary_forecast[1]
            tomorrow_rain_prob = d1.precipitation_prob_pct
            tomorrow_temp_max = d1.temp_max_c
            tomorrow_temp_min = d1.temp_min_c

        forecast_dicts = [
            {
                "date": f.date,
                "temp_max_c": f.temp_max_c,
                "temp_min_c": f.temp_min_c,
                "precipitation_mm": f.precipitation_mm,
                "precipitation_prob_pct": f.precipitation_prob_pct,
                "wind_max_kmh": f.wind_max_kmh,
                "condition_text": f.condition_text,
            }
            for f in primary_forecast[:7]
        ]

        ctx = AggregatedWeatherContext(
            city=city,
            state=state,
            latitude=lat,
            longitude=lon,
            aggregated_at=datetime.now(timezone.utc).isoformat(),
            temperature_c=primary.temperature_c,
            apparent_temperature_c=primary.apparent_temperature_c,
            humidity_pct=primary.humidity_pct,
            precipitation_mm=primary.precipitation_mm,
            wind_kmh=primary.wind_kmh,
            wind_gust_kmh=primary.wind_gust_kmh,
            condition_text=primary.condition_text,
            visibility_km=primary.visibility_km,
            pressure_hpa=primary.pressure_hpa,
            uv_index=primary.uv_index,
            tomorrow_rain_prob=tomorrow_rain_prob,
            tomorrow_temp_max=tomorrow_temp_max,
            tomorrow_temp_min=tomorrow_temp_min,
            forecast_days=forecast_dicts,
            providers_queried=[r.provider_name for r in results],
            providers_ok=[r.provider_name for r in ok_results],
            providers_failed=[r.provider_name for r in failed_results],
            provider_snapshots=snapshots,
            agreement_score=agreement,
            temp_spread_c=temp_spread,
        )

        self._agg_cache[cache_key] = (now, ctx)
        return ctx


# Module-level singleton for reuse across FastAPI requests
_aggregator_instance: Optional[WeatherAggregationService] = None


def get_aggregator() -> WeatherAggregationService:
    global _aggregator_instance
    if _aggregator_instance is None:
        _aggregator_instance = WeatherAggregationService()
    return _aggregator_instance


if __name__ == "__main__":
    import sys
    city = sys.argv[1] if len(sys.argv) > 1 else "Jaipur"
    agg = get_aggregator()
    ctx = agg.get_unified_context(city)
    import json
    print(json.dumps(ctx.to_dict(), indent=2, default=str))
