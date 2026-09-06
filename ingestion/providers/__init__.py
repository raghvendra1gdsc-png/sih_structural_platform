"""ingestion/providers — Weather provider adapter registry."""
from ingestion.providers.base import (
    WeatherProvider, ProviderResult, ProviderHealth,
    NormalizedConditions, NormalizedForecastDay,
)
from ingestion.providers.open_meteo import OpenMeteoProvider
from ingestion.providers.openweather import OpenWeatherProvider
from ingestion.providers.tomorrow import TomorrowProvider
from ingestion.providers.weatherapi import WeatherAPIProvider

__all__ = [
    "WeatherProvider", "ProviderResult", "ProviderHealth",
    "NormalizedConditions", "NormalizedForecastDay",
    "OpenMeteoProvider", "OpenWeatherProvider",
    "TomorrowProvider", "WeatherAPIProvider",
]
