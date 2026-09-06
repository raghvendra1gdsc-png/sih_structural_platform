"""
ingestion/providers/base.py
===========================
Abstract base for all weather data providers.
Every provider normalises its data to NormalizedConditions / NormalizedForecastDay
so the aggregation layer can compare across providers without knowing internals.
"""
from __future__ import annotations
import abc
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class NormalizedConditions:
    """Unified current-conditions schema — all providers normalise to this."""
    temperature_c: float
    apparent_temperature_c: Optional[float] = None
    humidity_pct: Optional[int] = None
    precipitation_mm: float = 0.0
    wind_kmh: float = 0.0
    wind_gust_kmh: Optional[float] = None
    wind_direction_deg: Optional[int] = None
    weather_code: Optional[int] = None
    condition_text: str = "Unknown"
    visibility_km: Optional[float] = None
    pressure_hpa: Optional[float] = None
    uv_index: Optional[float] = None


@dataclass
class NormalizedForecastDay:
    """Single-day forecast normalised across providers."""
    date: str                        # YYYY-MM-DD
    temp_max_c: float
    temp_min_c: float
    precipitation_mm: float = 0.0
    precipitation_prob_pct: int = 0
    wind_max_kmh: float = 0.0
    wind_gust_max_kmh: Optional[float] = None
    uv_index: Optional[float] = None
    condition_text: str = "Unknown"
    weather_code: Optional[int] = None



@dataclass
class ProviderResult:
    """Container returned by every provider's get() call."""
    provider_name: str
    fetched_at: datetime
    is_cached: bool
    current: Optional[NormalizedConditions] = None
    forecast_days: list[NormalizedForecastDay] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.current is not None


@dataclass
class ProviderHealth:
    """Live health state of a single provider."""
    provider_name: str
    is_up: bool = True
    consecutive_failures: int = 0
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_error: Optional[str] = None
    total_requests: int = 0
    total_failures: int = 0

    def record_success(self) -> None:
        self.is_up = True
        self.consecutive_failures = 0
        self.last_success_at = datetime.now(timezone.utc)
        self.total_requests += 1

    def record_failure(self, error: str) -> None:
        self.consecutive_failures += 1
        self.total_failures += 1
        self.total_requests += 1
        self.last_failure_at = datetime.now(timezone.utc)
        self.last_error = error
        if self.consecutive_failures >= 3:
            self.is_up = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "is_up": self.is_up,
            "consecutive_failures": self.consecutive_failures,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_failure_at": self.last_failure_at.isoformat() if self.last_failure_at else None,
            "last_error": self.last_error,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
        }


class WeatherProvider(abc.ABC):
    """
    Abstract base for all weather providers.
    Handles in-process caching and health tracking.
    Subclasses implement _fetch_current() and _fetch_forecast().
    """

    def __init__(self, cache_ttl_seconds: int = 1800) -> None:
        self.cache_ttl = cache_ttl_seconds
        self.health = ProviderHealth(provider_name=self.name)
        self._cache: dict[str, tuple[float, ProviderResult]] = {}

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Stable provider slug (e.g. 'open_meteo', 'openweather')."""

    @abc.abstractmethod
    def _fetch_current(self, lat: float, lon: float) -> NormalizedConditions:
        """Fetch live current conditions. Raises on failure."""

    @abc.abstractmethod
    def _fetch_forecast(self, lat: float, lon: float) -> list[NormalizedForecastDay]:
        """Fetch multi-day forecast. Raises on failure."""

    def _cache_key(self, lat: float, lon: float) -> str:
        return f"{self.name}:{round(lat, 2)}:{round(lon, 2)}"

    def _get_cached(self, key: str) -> Optional[ProviderResult]:
        if key in self._cache:
            ts, result = self._cache[key]
            if time.time() - ts < self.cache_ttl:
                return result
        return None

    def _set_cached(self, key: str, result: ProviderResult) -> None:
        self._cache[key] = (time.time(), result)

    def is_configured(self) -> bool:
        """Return True if required API keys / configuration are available."""
        return True


    def get(self, lat: float, lon: float, use_cache: bool = True) -> ProviderResult:
        """
        Public entry point. Returns fresh or cached ProviderResult.
        Never raises — failures are captured in result.error.
        """
        key = self._cache_key(lat, lon)
        if use_cache:
            cached = self._get_cached(key)
            if cached:
                return ProviderResult(
                    provider_name=self.name,
                    fetched_at=cached.fetched_at,
                    is_cached=True,
                    current=cached.current,
                    forecast_days=cached.forecast_days,
                )


        try:
            current = self._fetch_current(lat, lon)
            forecast = self._fetch_forecast(lat, lon)
            result = ProviderResult(
                provider_name=self.name,
                fetched_at=datetime.now(timezone.utc),
                is_cached=False,
                current=current,
                forecast_days=forecast,
            )
            self._set_cached(key, result)
            self.health.record_success()
            return result
        except Exception as exc:
            err_msg = f"{type(exc).__name__}: {exc}"
            logger.warning("[%s] fetch failed (%.2f, %.2f): %s", self.name, lat, lon, err_msg)
            self.health.record_failure(err_msg)
            return ProviderResult(
                provider_name=self.name,
                fetched_at=datetime.now(timezone.utc),
                is_cached=False,
                error=err_msg,
            )
