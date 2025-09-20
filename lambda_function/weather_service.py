"""
Weather service layer with caching and business logic.
"""

import os
import logging
from datetime import datetime, timezone
from typing import List, Dict
from external_api import (
    OpenWeatherMapClient,
    WeatherAPIError,
    OpenWeatherMapResponse,
)
from models import WeatherResponse, BatchWeatherResponse
from cache_service import DynamoDBCacheService, CacheError

logger = logging.getLogger(__name__)


class WeatherService:
    """
    Weather service that handles business logic and caching.
    """

    def __init__(self, api_key: str):
        """
        Initialize the weather service.

        Args:
            api_key: OpenWeatherMap API key
        """
        self.api_client = OpenWeatherMapClient(api_key)

        # Initialize DynamoDB cache service
        try:
            ttl_minutes = int(os.getenv("CACHE_TTL_MINUTES", "10"))
            self.cache_service = DynamoDBCacheService(ttl_minutes=ttl_minutes)
            logger.info("DynamoDB cache service initialized successfully")
        except (CacheError, ValueError) as e:
            logger.warning(
                "Failed to initialize cache service: %s. Proceeding without cache.", e
            )
            self.cache_service = None

    async def get_weather(self, city: str) -> WeatherResponse:
        """
        Get weather information for a single city.

        Args:
            city: Name of the city

        Returns:
            WeatherResponse: Formatted weather data

        Raises:
            WeatherAPIError: If weather data cannot be retrieved
        """
        try:
            # Check cache first
            if self.cache_service:
                cached_response = await self.cache_service.get_weather(city)
                if cached_response:
                    logger.debug("Returning cached weather for %s", city)
                    return cached_response

            # Cache miss - fetch from API
            weather_data = await self.api_client.get_weather(city)

            # Convert to our internal format
            response = self._convert_to_weather_response(weather_data)

            # Cache the response
            if self.cache_service:
                await self.cache_service.set_weather(response)

            return response

        except WeatherAPIError:
            # Re-raise API errors as-is
            raise
        except Exception as e:
            logger.error("Unexpected error in weather service for %s: %s", city, str(e))
            raise WeatherAPIError(f"Service error for {city}") from e

    async def get_batch_weather(
        self, cities: List[str], max_cities: int = 10
    ) -> BatchWeatherResponse:
        """
        Get weather information for multiple cities.

        Args:
            cities: List of city names
            max_cities: Maximum number of cities allowed in batch

        Returns:
            BatchWeatherResponse: Batch weather data with statistics

        Raises:
            WeatherAPIError: If batch request is invalid
        """
        if not cities:
            raise WeatherAPIError("Cities list cannot be empty")

        if len(cities) > max_cities:
            raise WeatherAPIError(
                f"Maximum {max_cities} cities allowed per batch request"
            )

        # Remove duplicates while preserving order
        unique_cities = list(dict.fromkeys(cities))

        try:
            # Check cache for all cities first
            cached_results = {}
            cities_to_fetch = unique_cities

            if self.cache_service:
                cached_results = await self.cache_service.batch_get_weather(
                    unique_cities
                )
                cities_to_fetch = [
                    city for city in unique_cities if city not in cached_results
                ]
                logger.debug(
                    "Cache hit for %d cities, need to fetch %d cities",
                    len(cached_results),
                    len(cities_to_fetch),
                )

            # Fetch remaining cities from API
            api_results = {}
            if cities_to_fetch:
                weather_data_map = await self.api_client.get_batch_weather(
                    cities_to_fetch
                )

                # Convert API responses to our format
                for city in cities_to_fetch:
                    if city in weather_data_map:
                        weather_response = self._convert_to_weather_response(
                            weather_data_map[city]
                        )
                        api_results[city] = weather_response

                # Cache the new results
                if self.cache_service and api_results:
                    await self.cache_service.batch_set_weather(
                        list(api_results.values())
                    )

            # Combine cached and fresh results
            results = []
            for city in unique_cities:
                if city in cached_results:
                    results.append(cached_results[city])
                elif city in api_results:
                    results.append(api_results[city])

            return BatchWeatherResponse(
                results=results,
                total_cities=len(unique_cities),
                successful_requests=len(results),
            )

        except Exception as e:
            logger.error("Unexpected error in batch weather service: %s", str(e))
            raise WeatherAPIError("Batch service error") from e

    async def health_check(self) -> Dict[str, any]:
        """
        Perform health check of the weather service.

        Returns:
            Dict with health status information
        """
        try:
            api_healthy = await self.api_client.health_check()

            # Cache health check will be added with caching implementation
            cache_healthy = True  # Placeholder

            overall_healthy = api_healthy and cache_healthy

            return {
                "status": "healthy" if overall_healthy else "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "checks": {
                    "openweathermap_api": "healthy" if api_healthy else "unhealthy",
                    "cache": "healthy" if cache_healthy else "unhealthy",
                },
            }

        except (WeatherAPIError, ValueError) as e:
            logger.error("Health check failed: %s", str(e))
            return {
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }

    def _convert_to_weather_response(
        self, api_response: OpenWeatherMapResponse
    ) -> WeatherResponse:
        """
        Convert OpenWeatherMap API response to our internal format.

        Args:
            api_response: Response from OpenWeatherMap API

        Returns:
            WeatherResponse: Our standardized weather response
        """
        return WeatherResponse(
            city=api_response.name,
            temperature=round(api_response.temperature, 1),
            description=api_response.description.title(),
            humidity=api_response.humidity,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
