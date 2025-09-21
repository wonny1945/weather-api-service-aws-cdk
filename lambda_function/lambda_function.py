"""
AWS Lambda handler with FastAPI application for weather API service.
"""

import logging
import os
from datetime import datetime

from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyQuery, APIKeyHeader
from fastapi.openapi.docs import get_swagger_ui_html
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

# Define API key security schemes
api_key_query = APIKeyQuery(name="api_key", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key(
    query_key: str = Security(api_key_query),
    header_key: str = Security(api_key_header),
) -> str:
    """Extract API key from query parameter or header."""
    api_key = query_key or header_key
    if not api_key or not api_key.strip():
        raise HTTPException(status_code=400, detail="API key is required")
    return api_key.strip()


# Initialize FastAPI app
app = FastAPI(
    title="Weather API Service",
    description="Serverless weather API service",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom OpenAPI endpoint without API key requirement
@app.get("/openapi.json", include_in_schema=False)
async def custom_openapi():
    """Return OpenAPI specification without requiring API key."""
    return app.openapi()


# Custom Swagger UI endpoint without API key requirement
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    """Return Swagger UI without requiring API key."""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Weather API Documentation",
    )


# Health check endpoint
@app.get("/health")
async def health_check(api_key: str = Security(get_api_key)):
    """Health check endpoint with API validation."""
    try:
        # Test with user's API key (already validated by security dependency)
        service = WeatherService(api_key)
        health_status = await service.health_check()
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
async def get_weather(city: str, api_key: str = Security(get_api_key)):
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
        # Create service with user's API key (already validated by security dependency)
        service = WeatherService(api_key)
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
async def get_batch_weather(
    request: BatchWeatherRequest, api_key: str = Security(get_api_key)
):
    """
    Get weather information for multiple cities.

    Args:
        request: BatchWeatherRequest containing list of cities
        api_key: OpenWeatherMap API key (from security dependency)

    Returns:
        BatchWeatherResponse: Weather information for all cities

    Raises:
        HTTPException: If request is invalid or service unavailable
    """
    try:
        # Create service with user's API key (already validated by security dependency)
        service = WeatherService(api_key)
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
