"""
External API client for OpenWeatherMap service.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

import aiohttp
from pydantic import BaseModel, Field

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
    Asynchronous client for OpenWeatherMap API.
    """

    def __init__(self, api_key: str, timeout: int = 10):
        """
        Initialize the OpenWeatherMap client.

        Args:
            api_key: OpenWeatherMap API key
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def get_weather(self, city: str) -> OpenWeatherMapResponse:
        """
        Get weather data for a single city.

        Args:
            city: Name of the city

        Returns:
            OpenWeatherMapResponse: Weather data

        Raises:
            WeatherAPIError: If API request fails
        """
        if not city or not city.strip():
            raise WeatherAPIError("City name cannot be empty")

        params = {
            "q": city.strip(),
            "appid": self.api_key,
        }

        url = f"{self.base_url}/weather"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                logger.info("Requesting weather data for city: %s", city)

                async with session.get(url, params=params) as response:
                    response_data = await response.json()

                    if response.status == 200:
                        logger.info("Successfully fetched weather for %s", city)
                        return OpenWeatherMapResponse(**response_data)

                    if response.status == 404:
                        error_msg = f"City '{city}' not found"
                        logger.warning(error_msg)
                        raise WeatherAPIError(error_msg, status_code=404)

                    if response.status == 401:
                        error_msg = "Invalid API key"
                        logger.error(error_msg)
                        raise WeatherAPIError(error_msg, status_code=401)

                    # For other status codes
                    error_msg = response_data.get("message", "Unknown API error")
                    logger.error(
                        "API error for %s: %s (status: %d)",
                        city,
                        error_msg,
                        response.status,
                    )
                    raise WeatherAPIError(error_msg, status_code=response.status)

        except aiohttp.ClientError as e:
            error_msg = f"Network error while fetching weather for {city}: {str(e)}"
            logger.error(error_msg)
            raise WeatherAPIError(error_msg) from e

        except asyncio.TimeoutError as e:
            error_msg = f"Timeout while fetching weather for {city}"
            logger.error(error_msg)
            raise WeatherAPIError(error_msg) from e

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
            # Use a known city for health check
            await self.get_weather("London")
            return True
        except WeatherAPIError:
            return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error("Health check failed: %s", str(e))
            return False
