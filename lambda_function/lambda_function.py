"""
AWS Lambda handler with FastAPI application for weather API service.
"""

import logging
import os
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from external_api import WeatherAPIError
from weather_service import WeatherService
from models import (
    WeatherResponse,
    BatchWeatherRequest,
    BatchWeatherResponse,
)

# Simple configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
MAX_BATCH_CITIES = 10

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Note: Weather service is now created per-request with user's API key
# No global service instance needed

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


# Health check endpoint
@app.get("/health")
async def health_check(api_key: str = None):
    """Health check endpoint with optional API validation."""
    try:
        if api_key:
            # Test with user's API key
            service = WeatherService(api_key.strip())
            health_status = await service.health_check()
        else:
            # Basic service health without API key
            health_status = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "message": (
                    "Service is running " "(no API key provided for external API test)"
                ),
            }
        return health_status
    except (WeatherAPIError, ValueError) as e:
        logger.error("Health check failed: %s", str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint providing API information."""
    return {
        "service": "Weather API Service",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "single_weather": "/weather/{city}?api_key=YOUR_API_KEY",
            "batch_weather": "/weather/batch",
            "health_check": "/health?api_key=YOUR_API_KEY",
            "documentation": "/docs",
        },
    }


# Single city weather endpoint
@app.get("/weather/{city}", response_model=WeatherResponse)
async def get_weather(city: str, api_key: str):
    """
    Get weather information for a single city.

    Args:
        city: Name of the city to get weather for
        api_key: OpenWeatherMap API key

    Returns:
        WeatherResponse: Weather information for the specified city

    Raises:
        HTTPException: If city is not found or service unavailable
    """
    try:
        # Validate API key
        if not api_key or not api_key.strip():
            raise HTTPException(status_code=400, detail="API key is required")

        # Create service with user's API key
        service = WeatherService(api_key.strip())
        weather_data = await service.get_weather(city)
        return weather_data

    except HTTPException:
        # Re-raise HTTP exceptions as-is (e.g., API key validation errors)
        raise

    except WeatherAPIError as e:
        logger.warning("Weather API error for %s: %s", city, str(e))
        if e.status_code == 404:
            raise HTTPException(
                status_code=404, detail=f"City '{city}' not found"
            ) from e
        if e.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid API key") from e
        # For other status codes
        raise HTTPException(
            status_code=503, detail="Weather service unavailable"
        ) from e

    except Exception as e:
        logger.error("Unexpected error fetching weather for %s: %s", city, str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch weather data for {city}"
        ) from e


# Batch weather endpoint
@app.post("/weather/batch", response_model=BatchWeatherResponse)
async def get_batch_weather(request: BatchWeatherRequest):
    """
    Get weather information for multiple cities.

    Args:
        request: BatchWeatherRequest containing list of cities and API key

    Returns:
        BatchWeatherResponse: Weather information for all cities

    Raises:
        HTTPException: If request is invalid or service unavailable
    """
    try:
        # Validate API key
        if not request.api_key or not request.api_key.strip():
            raise HTTPException(status_code=400, detail="API key is required")

        # Create service with user's API key
        service = WeatherService(request.api_key.strip())
        batch_data = await service.get_batch_weather(request.cities, MAX_BATCH_CITIES)
        return batch_data

    except HTTPException:
        # Re-raise HTTP exceptions as-is (e.g., API key validation errors)
        raise

    except WeatherAPIError as e:
        logger.warning("Weather API error in batch request: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e

    except Exception as e:
        logger.error("Unexpected error in batch weather request: %s", str(e))
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
lambda_handler = Mangum(app, lifespan="off")
