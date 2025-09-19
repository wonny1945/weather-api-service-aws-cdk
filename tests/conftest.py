"""
Pytest configuration and shared fixtures.
"""

import pytest
import asyncio
from typing import Generator


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create an event loop for the test session.
    This ensures async tests run properly.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_api_key() -> str:
    """Sample API key for testing."""
    return "test_openweather_api_key_123"


@pytest.fixture
def sample_cities() -> list[str]:
    """Sample city names for testing."""
    return ["Seoul", "Tokyo", "New York", "London", "Paris"]


@pytest.fixture
def sample_weather_data() -> dict:
    """Sample weather data structure."""
    return {
        "city": "Seoul",
        "temperature": 22.5,
        "description": "Partly Cloudy",
        "humidity": 65,
        "timestamp": "2024-01-01T12:00:00Z",
    }


@pytest.fixture
def sample_batch_request_data(sample_api_key, sample_cities) -> dict:
    """Sample batch request data."""
    return {"cities": sample_cities[:3], "api_key": sample_api_key}  # First 3 cities


@pytest.fixture
def mock_openweather_response() -> dict:
    """Mock OpenWeatherMap API response."""
    return {
        "name": "Seoul",
        "main": {"temp": 295.65, "humidity": 65, "pressure": 1013},  # 22.5°C in Kelvin
        "weather": [{"main": "Clouds", "description": "partly cloudy", "icon": "02d"}],
        "dt": 1640995200,
        "sys": {"country": "KR"},
    }
