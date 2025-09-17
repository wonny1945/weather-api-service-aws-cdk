"""
AWS Lambda handler with FastAPI application for weather API service.
"""

import logging
import os
from typing import List
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel

# Simple configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
MAX_BATCH_CITIES = 10

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Weather API Service",
    description="Serverless weather API service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request/response validation
class WeatherResponse(BaseModel):
    city: str
    temperature: float
    description: str
    humidity: int
    timestamp: str


class BatchWeatherRequest(BaseModel):
    cities: List[str]


class BatchWeatherResponse(BaseModel):
    results: List[WeatherResponse]
    total_cities: int
    successful_requests: int


class ErrorResponse(BaseModel):
    error: str
    message: str
    status_code: int


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint providing API information."""
    return {
        "service": "Weather API Service",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "single_weather": "/weather/{city}",
            "batch_weather": "/weather/batch",
            "documentation": "/docs",
        },
    }


# Single city weather endpoint
@app.get("/weather/{city}", response_model=WeatherResponse)
async def get_weather(city: str):
    """
    Get weather information for a single city.

    Args:
        city: Name of the city to get weather for

    Returns:
        WeatherResponse: Weather information for the specified city

    Raises:
        HTTPException: If city is not found or service unavailable
    """
    try:
        logger.info("Fetching weather for city: %s", city)

        # NOTE: Using mock data - will be replaced with OpenWeatherMap API
        # Provides consistent response structure for testing
        mock_weather = {
            "city": city,
            "temperature": 22.5,
            "description": "Partly cloudy",
            "humidity": 65,
            "timestamp": datetime.now().isoformat() + "Z",
        }

        logger.info("Successfully fetched weather for %s", city)
        return WeatherResponse(**mock_weather)

    except Exception as e:
        logger.error("Error fetching weather for %s: %s", city, str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch weather data for {city}"
        ) from e


# Batch weather endpoint
@app.post("/weather/batch", response_model=BatchWeatherResponse)
async def get_batch_weather(request: BatchWeatherRequest):
    """
    Get weather information for multiple cities.

    Args:
        request: BatchWeatherRequest containing list of cities

    Returns:
        BatchWeatherResponse: Weather information for all cities

    Raises:
        HTTPException: If request is invalid or service unavailable
    """
    try:
        logger.info("Fetching weather for %d cities", len(request.cities))

        if not request.cities:
            raise HTTPException(status_code=400, detail="Cities list cannot be empty")

        if len(request.cities) > MAX_BATCH_CITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {MAX_BATCH_CITIES} cities allowed per batch request",
            )

        # NOTE: Using mock data for batch - will be replaced with concurrent API calls
        # Ensures consistent testing of batch endpoint logic
        results = []
        successful_requests = 0

        for city in request.cities:
            try:
                mock_weather = {
                    "city": city,
                    "temperature": 22.5,
                    "description": "Partly cloudy",
                    "humidity": 65,
                    "timestamp": datetime.now().isoformat() + "Z",
                }
                results.append(WeatherResponse(**mock_weather))
                successful_requests += 1
            except (ValueError, TypeError, KeyError) as e:
                logger.warning("Failed to fetch weather for %s: %s", city, str(e))
                # Continue processing other cities

        logger.info(
            "Successfully processed %d/%d cities",
            successful_requests,
            len(request.cities),
        )

        return BatchWeatherResponse(
            results=results,
            total_cities=len(request.cities),
            successful_requests=successful_requests,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in batch weather request: %s", str(e))
        raise HTTPException(
            status_code=500, detail="Failed to process batch weather request"
        ) from e


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):  # pylint: disable=unused-argument
    """Global exception handler for unhandled errors."""
    logger.error("Unhandled exception: %s", str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "status_code": 500,
        },
    )


# AWS Lambda handler using Mangum
handler = Mangum(app, lifespan="off")
