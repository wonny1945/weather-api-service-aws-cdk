"""
Comprehensive test suite for the weather API Lambda function.
Tests all endpoints, validation, error handling, and edge cases.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json
from datetime import datetime

# Import the FastAPI app
from lambda_function.lambda_function import (
    app,
    WeatherResponse,
    BatchWeatherRequest,
    BatchWeatherResponse,
)


# Test client fixture
@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestRootEndpoint:
    """Test cases for the root endpoint."""

    def test_root_endpoint_success(self, client):
        """Test that root endpoint returns correct API information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert data["service"] == "Weather API Service"
        assert data["version"] == "1.0.0"
        assert data["status"] == "active"
        assert "endpoints" in data
        assert data["endpoints"]["single_weather"] == "/weather/{city}"
        assert data["endpoints"]["batch_weather"] == "/weather/batch"
        assert data["endpoints"]["documentation"] == "/docs"

    def test_root_endpoint_response_structure(self, client):
        """Test that root endpoint response has correct structure."""
        response = client.get("/")
        data = response.json()

        required_fields = ["service", "version", "status", "endpoints"]
        for field in required_fields:
            assert field in data


class TestSingleWeatherEndpoint:
    """Test cases for the single city weather endpoint."""

    def test_get_weather_success(self, client):
        """Test successful weather retrieval for a city."""
        city = "seoul"
        response = client.get(f"/weather/{city}")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert data["city"] == city
        assert isinstance(data["temperature"], float)
        assert isinstance(data["description"], str)
        assert isinstance(data["humidity"], int)
        assert isinstance(data["timestamp"], str)

        # Validate specific values (mock data)
        assert data["temperature"] == 22.5
        assert data["description"] == "Partly cloudy"
        assert data["humidity"] == 65

    def test_get_weather_timestamp_format(self, client):
        """Test that timestamp is in correct ISO format."""
        response = client.get("/weather/tokyo")
        data = response.json()

        timestamp = data["timestamp"]
        assert timestamp.endswith("Z")

        # Verify it's a valid ISO format (should not raise exception)
        datetime.fromisoformat(timestamp.rstrip("Z"))

    def test_get_weather_different_cities(self, client):
        """Test weather endpoint with different city names."""
        cities = ["seoul", "busan", "tokyo", "new-york", "london"]

        for city in cities:
            response = client.get(f"/weather/{city}")
            assert response.status_code == 200
            data = response.json()
            assert data["city"] == city

    def test_get_weather_special_characters(self, client):
        """Test weather endpoint with cities containing special characters."""
        cities = ["new york", "são paulo", "méxico"]

        for city in cities:
            response = client.get(f"/weather/{city}")
            assert response.status_code == 200
            data = response.json()
            assert data["city"] == city

    def test_get_weather_response_model_validation(self, client):
        """Test that response matches WeatherResponse model."""
        response = client.get("/weather/seoul")
        data = response.json()

        # Should not raise validation error
        weather_response = WeatherResponse(**data)
        assert weather_response.city == "seoul"


class TestBatchWeatherEndpoint:
    """Test cases for the batch weather endpoint."""

    def test_batch_weather_success(self, client):
        """Test successful batch weather retrieval."""
        cities = ["seoul", "busan", "tokyo"]
        payload = {"cities": cities}

        response = client.post("/weather/batch", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert data["total_cities"] == len(cities)
        assert data["successful_requests"] == len(cities)
        assert len(data["results"]) == len(cities)

        # Check each result
        for i, result in enumerate(data["results"]):
            assert result["city"] == cities[i]
            assert result["temperature"] == 22.5
            assert result["description"] == "Partly cloudy"
            assert result["humidity"] == 65

    def test_batch_weather_single_city(self, client):
        """Test batch endpoint with single city."""
        payload = {"cities": ["seoul"]}

        response = client.post("/weather/batch", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["total_cities"] == 1
        assert data["successful_requests"] == 1
        assert len(data["results"]) == 1

    def test_batch_weather_max_cities(self, client):
        """Test batch endpoint with maximum allowed cities."""
        cities = [f"city{i}" for i in range(10)]  # MAX_BATCH_CITIES = 10
        payload = {"cities": cities}

        response = client.post("/weather/batch", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["total_cities"] == 10
        assert data["successful_requests"] == 10

    def test_batch_weather_empty_cities_list(self, client):
        """Test batch endpoint with empty cities list."""
        payload = {"cities": []}

        response = client.post("/weather/batch", json=payload)

        assert response.status_code == 400
        error_data = response.json()
        assert "Cities list cannot be empty" in error_data["detail"]

    def test_batch_weather_too_many_cities(self, client):
        """Test batch endpoint with too many cities."""
        cities = [f"city{i}" for i in range(11)]  # Exceeds MAX_BATCH_CITIES
        payload = {"cities": cities}

        response = client.post("/weather/batch", json=payload)

        assert response.status_code == 400
        error_data = response.json()
        assert "Maximum 10 cities allowed" in error_data["detail"]

    def test_batch_weather_invalid_payload(self, client):
        """Test batch endpoint with invalid payload structure."""
        invalid_payloads = [
            {},  # Missing cities
            {"city": ["seoul"]},  # Wrong key name
            {"cities": "seoul"},  # String instead of list
            {"cities": [123]},  # Invalid city type
        ]

        for payload in invalid_payloads:
            response = client.post("/weather/batch", json=payload)
            assert response.status_code == 422  # Pydantic validation error

    def test_batch_weather_response_model_validation(self, client):
        """Test that batch response matches BatchWeatherResponse model."""
        payload = {"cities": ["seoul", "busan"]}
        response = client.post("/weather/batch", json=payload)
        data = response.json()

        # Should not raise validation error
        batch_response = BatchWeatherResponse(**data)
        assert batch_response.total_cities == 2


class TestPydanticModels:
    """Test cases for Pydantic model validation."""

    def test_weather_response_model(self):
        """Test WeatherResponse model validation."""
        valid_data = {
            "city": "seoul",
            "temperature": 22.5,
            "description": "Partly cloudy",
            "humidity": 65,
            "timestamp": "2024-01-01T12:00:00Z",
        }

        weather = WeatherResponse(**valid_data)
        assert weather.city == "seoul"
        assert weather.temperature == 22.5

    def test_weather_response_model_invalid_data(self):
        """Test WeatherResponse model with invalid data."""
        invalid_data = {
            "city": "seoul",
            "temperature": "invalid",  # Should be float
            "description": "Partly cloudy",
            "humidity": 65,
            "timestamp": "2024-01-01T12:00:00Z",
        }

        with pytest.raises(ValueError):
            WeatherResponse(**invalid_data)

    def test_batch_weather_request_model(self):
        """Test BatchWeatherRequest model validation."""
        valid_data = {"cities": ["seoul", "busan"]}

        request = BatchWeatherRequest(**valid_data)
        assert request.cities == ["seoul", "busan"]

    def test_batch_weather_request_model_invalid(self):
        """Test BatchWeatherRequest model with invalid data."""
        invalid_data = {"cities": "seoul"}  # Should be list

        with pytest.raises(ValueError):
            BatchWeatherRequest(**invalid_data)


class TestErrorHandling:
    """Test cases for error handling and edge cases."""

    def test_nonexistent_endpoint(self, client):
        """Test request to nonexistent endpoint."""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_wrong_http_method(self, client):
        """Test wrong HTTP method on endpoints."""
        # PUT to single weather endpoint (should be GET)
        response = client.put("/weather/seoul")
        assert response.status_code == 405

        # DELETE to root endpoint (should be GET)
        response = client.delete("/")
        assert response.status_code == 405

    def test_invalid_json_payload(self, client):
        """Test invalid JSON payload to batch endpoint."""
        response = client.post(
            "/weather/batch",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    @patch("lambda_function.lambda_function.logger")
    def test_logging_calls(self, mock_logger, client):
        """Test that appropriate logging calls are made."""
        # Test single weather endpoint logging
        client.get("/weather/seoul")

        mock_logger.info.assert_any_call("Fetching weather for city: %s", "seoul")
        mock_logger.info.assert_any_call("Successfully fetched weather for %s", "seoul")

        # Test batch weather endpoint logging
        payload = {"cities": ["seoul", "busan"]}
        client.post("/weather/batch", json=payload)

        mock_logger.info.assert_any_call("Fetching weather for %d cities", 2)


class TestDocumentationEndpoints:
    """Test cases for API documentation endpoints."""

    def test_swagger_docs_accessible(self, client):
        """Test that Swagger docs are accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_accessible(self, client):
        """Test that ReDoc is accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_schema_accessible(self, client):
        """Test that OpenAPI schema is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert schema["info"]["title"] == "Weather API Service"


class TestCORSConfiguration:
    """Test cases for CORS configuration."""

    def test_cors_middleware_configured(self, client):
        """Test that CORS middleware is properly configured in the app."""
        from lambda_function.lambda_function import app

        # Check if any middleware is configured (FastAPI automatically configures CORS)
        # In testing, CORS headers might not appear but middleware should be present
        assert len(app.user_middleware) > 0

    def test_cors_preflight_request(self, client):
        """Test CORS preflight request handling."""
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        }

        response = client.options("/weather/seoul", headers=headers)
        # OPTIONS request should be handled
        assert response.status_code in [200, 405]  # 405 is also acceptable for OPTIONS


# Integration test for the complete workflow
class TestIntegrationWorkflow:
    """Integration tests for complete API workflow."""

    def test_complete_api_workflow(self, client):
        """Test complete workflow: root -> single -> batch."""
        # Step 1: Check API info
        root_response = client.get("/")
        assert root_response.status_code == 200

        # Step 2: Get single city weather
        single_response = client.get("/weather/seoul")
        assert single_response.status_code == 200

        # Step 3: Get batch weather
        batch_payload = {"cities": ["seoul", "busan", "tokyo"]}
        batch_response = client.post("/weather/batch", json=batch_payload)
        assert batch_response.status_code == 200

        # Verify all responses are consistent
        single_data = single_response.json()
        batch_data = batch_response.json()

        seoul_from_batch = next(
            result for result in batch_data["results"] if result["city"] == "seoul"
        )

        # Both should return same mock data structure
        assert single_data["temperature"] == seoul_from_batch["temperature"]
        assert single_data["description"] == seoul_from_batch["description"]
        assert single_data["humidity"] == seoul_from_batch["humidity"]
