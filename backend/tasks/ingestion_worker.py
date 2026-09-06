"""
backend/tasks/ingestion_worker.py
==================================
Phase 0 stub — Celery worker placeholder.
Phase 1 will implement USGS polling and normalisation tasks here.
"""

import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = Celery(
    "ingestion_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@app.task(name="ingestion.health_check")
def health_check() -> dict:
    """Phase 0 placeholder task — verifies Celery worker is reachable."""
    return {"status": "ok", "phase": "0-stub"}


# Register weather ingestion tasks
try:
    import backend.tasks.weather_ingestion  # noqa: F401
except ImportError:
    pass

