"""
backend/api/weather_gpt.py
==========================
Grounded WeatherGPT conversational intelligence REST endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.weather_api_schemas import (
    WeatherGPTQueryPayload,
    WeatherGPTResponse,
)
from backend.services.weather_gpt_service import WeatherGPTService

router = APIRouter(prefix="/api/chat", tags=["weathergpt"])


@router.post("/weathergpt", response_model=WeatherGPTResponse)
def query_weathergpt(
    payload: WeatherGPTQueryPayload,
    db: Session = Depends(get_db),
) -> WeatherGPTResponse:
    """
    Query the grounded WeatherGPT conversational assistant.
    Combines numerical forecasts with real platform observations and incident metrics.
    """
    if not payload.query or len(payload.query.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query must contain at least 2 characters.",
        )

    service = WeatherGPTService(db)
    result = service.answer_question(payload.query)
    return WeatherGPTResponse.model_validate(result)
