"""
Pydantic models for request/response validation.
"""

from typing import List
from pydantic import BaseModel


class WeatherResponse(BaseModel):
    """Response model for single city weather data."""

    city: str
    temperature: float
    description: str
    humidity: int
    timestamp: str


class BatchWeatherRequest(BaseModel):
    """Request model for batch weather queries."""

    cities: List[str]
    api_key: str


class BatchWeatherResponse(BaseModel):
    """Response model for batch weather queries."""

    results: List[WeatherResponse]
    total_cities: int
    successful_requests: int


class ErrorResponse(BaseModel):
    """Response model for error cases."""

    error: str
    message: str
    status_code: int
