"""
External API client for OpenWeatherMap service.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

import aiohttp
from pydantic import BaseModel, Field

from config import RetryConfig, ExternalAPIConfig
from retry_service import RetryConfig as RetryConfigClass, api_retry

logger = logging.getLogger(__name__)


class WeatherAPIError(Exception):
    """Custom exception for weather API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class OpenWeatherMapResponse(BaseModel):
    """Model for OpenWeatherMap API response."""

    name: str = Field(..., description="City name")
    main: Dict[str, Any] = Field(..., description="Main weather data")
    weather: list = Field(..., description="Weather conditions")
    dt: int = Field(..., description="Data calculation time")

    @property
    def temperature(self) -> float:
        """Temperature in Celsius."""
        try:
            return self.main["temp"] - 273.15  # Convert from Kelvin
        except KeyError:
            return 0.0

    @property
    def humidity(self) -> int:
        """Humidity percentage."""
        try:
            return self.main["humidity"]
        except KeyError:
            return 0

    @property
    def description(self) -> str:
        """Weather description."""
        if self.weather:
            return self.weather[0].get("description", "Unknown")
        return "Unknown"


class OpenWeatherMapClient:
    """
    Asynchronous client for OpenWeatherMap API with retry logic.
    """

    def __init__(self, api_key: str, timeout: int = None):
        """
        Initialize the OpenWeatherMap client.

        Args:
            api_key: OpenWeatherMap API key
            timeout: Request timeout in seconds (defaults to config value)
        """
        self.api_key = api_key
        self.base_url = ExternalAPIConfig.OPENWEATHER_BASE_URL
        self.timeout = aiohttp.ClientTimeout(
            total=timeout or ExternalAPIConfig.OPENWEATHER_TIMEOUT
        )

        # Initialize retry configuration
        self.retry_config = RetryConfigClass(
            max_attempts=RetryConfig.API_MAX_ATTEMPTS,
            base_delay=RetryConfig.API_BASE_DELAY,
            backoff_multiplier=RetryConfig.API_BACKOFF_MULTIPLIER,
            max_delay=RetryConfig.API_MAX_DELAY,
            jitter=RetryConfig.API_JITTER,
            jitter_range=RetryConfig.API_JITTER_RANGE,
        )

    async def get_weather(self, city: str) -> OpenWeatherMapResponse:
        """
        Get weather data for a single city with retry logic.

        Args:
            city: Name of the city

        Returns:
            OpenWeatherMapResponse: Weather data

        Raises:
            WeatherAPIError: If API request fails after retries
        """

        # Apply retry decorator to the internal method
        @api_retry(self.retry_config)
        async def _get_weather_with_retry() -> OpenWeatherMapResponse:
            if not city or not city.strip():
                raise WeatherAPIError("City name cannot be empty")

            params = {
                "q": city.strip(),
                "appid": self.api_key,
            }

            url = f"{self.base_url}/weather"

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                logger.debug("Requesting weather data for city: %s", city)

                async with session.get(url, params=params) as response:
                    response_data = await response.json()

                    if response.status == 200:
                        logger.debug("Successfully fetched weather for %s", city)
                        return OpenWeatherMapResponse(**response_data)

                    if response.status == 404:
                        error_msg = f"City '{city}' not found"
                        logger.warning(error_msg)
                        raise WeatherAPIError(error_msg, status_code=404)

                    if response.status == 401:
                        error_msg = "Invalid API key"
                        logger.error(error_msg)
                        raise WeatherAPIError(error_msg, status_code=401)

                    # For other status codes (5xx will be retried, 4xx will not)
                    error_msg = response_data.get("message", "Unknown API error")
                    logger.error(
                        "API error for %s: %s (status: %d)",
                        city,
                        error_msg,
                        response.status,
                    )
                    # Create custom exception with status code for proper retry handling
                    if 500 <= response.status < 600:
                        # Server errors - should be retried
                        raise aiohttp.ClientResponseError(
                            request_info=None,
                            history=None,
                            status=response.status,
                            message=error_msg,
                        )

                    # Client errors - should not be retried
                    raise WeatherAPIError(error_msg, status_code=response.status)

        return await _get_weather_with_retry()

    async def get_batch_weather(
        self, cities: list[str]
    ) -> Dict[str, OpenWeatherMapResponse]:
        """
        Get weather data for multiple cities concurrently.

        Args:
            cities: List of city names

        Returns:
            Dict[str, OpenWeatherMapResponse]: Mapping of city to weather data
        """
        if not cities:
            return {}

        logger.info("Fetching weather for %d cities", len(cities))

        # Create concurrent tasks for all cities
        tasks = [self.get_weather(city) for city in cities]

        # Execute all requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        weather_data = {}
        for city, result in zip(cities, results):
            if isinstance(result, OpenWeatherMapResponse):
                weather_data[city] = result
            else:
                # Log the error but continue processing other cities
                logger.warning("Failed to fetch weather for %s: %s", city, str(result))

        logger.info(
            "Successfully fetched weather for %d/%d cities",
            len(weather_data),
            len(cities),
        )
        return weather_data

    async def health_check(self) -> bool:
        """
        Check if the OpenWeatherMap API is accessible.

        Returns:
            bool: True if API is accessible, False otherwise
        """
        try:
            # Use a known city for health check (with retry logic included)
            await self.get_weather("London")
            logger.info("OpenWeatherMap API health check passed")
            return True
        except WeatherAPIError as e:
            logger.warning("OpenWeatherMap API health check failed: %s", str(e))
            return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error("Network error during health check: %s", str(e))
            return False
