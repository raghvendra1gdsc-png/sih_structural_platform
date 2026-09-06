"""
backend/core/config.py — Application settings and configuration
National Weather Big Data Analytics Platform
"""

from __future__ import annotations

import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "National Weather Big Data Analytics Platform API"
    VERSION: str = "1.0.0-sih"
    DESCRIPTION: str = (
        "High-performance FastAPI backend providing geospatial weather analytics (PostGIS), "
        "AI weather-event classification, multimodal deduplication, source trust triage, "
        "incident hotspot clustering, and grounded WeatherGPT conversational intelligence."
    )

    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql://sih_user:sih_password@localhost:5432/weather_db",
        )
    )
    REDIS_URL: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    # --- Weather Data Providers ---
    OPENWEATHER_API_KEY: str = Field(
        default_factory=lambda: os.getenv("OPENWEATHER_API_KEY", "")
    )
    WEATHERAPI_KEY: str = Field(
        default_factory=lambda: os.getenv("WEATHERAPI_KEY", "")
    )
    TOMORROW_IO_API_KEY: str = Field(
        default_factory=lambda: os.getenv("TOMORROW_IO_API_KEY", "")
    )

    # --- LLM / AI Backend ---
    # "openai" | "gemini" | "none"
    LLM_BACKEND: str = Field(
        default_factory=lambda: os.getenv("LLM_BACKEND", "none")
    )
    OPENAI_API_KEY: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    OPENAI_MODEL: str = Field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )
    GOOGLE_AI_STUDIO_KEY: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_AI_STUDIO_KEY", "")
    )
    GEMINI_MODEL: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    )

    # --- Map Tiles ---
    MAPTILER_API_KEY: str = Field(
        default_factory=lambda: os.getenv("MAPTILER_API_KEY", "")
    )

    # --- Security ---
    SECRET_KEY: str = Field(
        default_factory=lambda: os.getenv("SECRET_KEY", "insecure-dev-default")
    )
    # CORS_ORIGINS is NOT read from .env to avoid pydantic-settings JSON parsing issues.
    # Edit this list directly or set it programmatically.
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*",
    ]


settings = Settings()
