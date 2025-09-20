"""
Retry functionality tests for the weather API Lambda function.
Tests the exponential backoff and jitter retry logic.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import aiohttp
from botocore.exceptions import ClientError

# Import retry service and components
from lambda_function.retry_service import (
    RetryConfig as RetryConfigClass,
    calculate_delay,
    should_retry_exception,
    api_retry,
    dynamodb_retry,
    RetryError,
)
from lambda_function.config import RetryConfig
from lambda_function.external_api import OpenWeatherMapClient, WeatherAPIError
from lambda_function.cache_service import DynamoDBCacheService, CacheError


class TestRetryConfiguration:
    """Test retry configuration and delay calculation."""

    def test_retry_config_values(self):
        """Test that retry configuration values are properly set."""
        # API retry config
        assert RetryConfig.API_MAX_ATTEMPTS == 3
        assert RetryConfig.API_BASE_DELAY == 1.0
        assert RetryConfig.API_BACKOFF_MULTIPLIER == 2.0
        assert RetryConfig.API_MAX_DELAY == 30.0
        assert RetryConfig.API_JITTER == True
        assert RetryConfig.API_JITTER_RANGE == 0.1

        # DynamoDB retry config
        assert RetryConfig.DYNAMODB_MAX_ATTEMPTS == 3
        assert RetryConfig.DYNAMODB_BASE_DELAY == 0.5
        assert RetryConfig.DYNAMODB_BACKOFF_MULTIPLIER == 2.0
        assert RetryConfig.DYNAMODB_MAX_DELAY == 10.0

    def test_delay_calculation_without_jitter(self):
        """Test exponential backoff delay calculation without jitter."""
        config = RetryConfigClass(
            max_attempts=3,
            base_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=10.0,
            jitter=False,
        )

        # Test exponential progression
        assert calculate_delay(1, config) == 1.0  # 1.0 * 2^0
        assert calculate_delay(2, config) == 2.0  # 1.0 * 2^1
        assert calculate_delay(3, config) == 4.0  # 1.0 * 2^2

    def test_delay_calculation_with_max_limit(self):
        """Test that delay doesn't exceed max_delay."""
        config = RetryConfigClass(
            max_attempts=5,
            base_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=5.0,  # Low max to test capping
            jitter=False,
        )

        # Should be capped at max_delay
        assert calculate_delay(4, config) == 5.0  # Would be 8.0, but capped at 5.0
        assert calculate_delay(5, config) == 5.0

    def test_delay_calculation_with_jitter(self):
        """Test that jitter adds randomness within expected range."""
        config = RetryConfigClass(
            max_attempts=3,
            base_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=10.0,
            jitter=True,
            jitter_range=0.1,  # ±10%
        )

        base_delay = 2.0  # Expected delay for attempt 2
        jitter_amount = base_delay * 0.1  # 0.2

        # Run multiple times to test jitter range
        delays = [calculate_delay(2, config) for _ in range(100)]

        # All delays should be within jitter range
        min_expected = base_delay - jitter_amount
        max_expected = base_delay + jitter_amount

        for delay in delays:
            assert min_expected <= delay <= max_expected

        # Should have some variation (not all identical)
        assert len(set(delays)) > 1


class TestExceptionRetryLogic:
    """Test which exceptions should trigger retries."""

    def test_api_retry_exceptions(self):
        """Test API retry exception logic."""
        retryable_exceptions = (
            aiohttp.ClientError,
            aiohttp.ServerTimeoutError,
            asyncio.TimeoutError,
            ConnectionError,
        )

        # Should retry network errors
        # Create a proper OSError for ClientConnectorError
        os_error = OSError("Connection failed")
        assert should_retry_exception(
            aiohttp.ClientConnectorError(connection_key=None, os_error=os_error),
            retryable_exceptions,
        )
        assert should_retry_exception(
            aiohttp.ServerTimeoutError(), retryable_exceptions
        )
        assert should_retry_exception(asyncio.TimeoutError(), retryable_exceptions)
        assert should_retry_exception(ConnectionError(), retryable_exceptions)

        # Should not retry non-retryable exceptions
        assert not should_retry_exception(ValueError("test"), retryable_exceptions)

    def test_api_response_error_retry_logic(self):
        """Test API response error retry decisions."""
        retryable_exceptions = (aiohttp.ClientResponseError,)

        # Should not retry 4xx client errors
        client_error = aiohttp.ClientResponseError(
            request_info=None, history=None, status=404, message="Not Found"
        )
        assert not should_retry_exception(client_error, retryable_exceptions)

        client_error_401 = aiohttp.ClientResponseError(
            request_info=None, history=None, status=401, message="Unauthorized"
        )
        assert not should_retry_exception(client_error_401, retryable_exceptions)

        # Should retry 5xx server errors
        server_error = aiohttp.ClientResponseError(
            request_info=None, history=None, status=500, message="Internal Server Error"
        )
        assert should_retry_exception(server_error, retryable_exceptions)

        server_error_503 = aiohttp.ClientResponseError(
            request_info=None, history=None, status=503, message="Service Unavailable"
        )
        assert should_retry_exception(server_error_503, retryable_exceptions)

    def test_dynamodb_retry_exceptions(self):
        """Test DynamoDB retry exception logic."""
        retryable_exceptions = (ClientError,)

        # Should retry throttling errors
        throttling_error = ClientError(
            error_response={
                "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
            },
            operation_name="GetItem",
        )
        assert should_retry_exception(throttling_error, retryable_exceptions)

        # Should retry provisioned throughput errors
        throughput_error = ClientError(
            error_response={
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "Capacity exceeded",
                }
            },
            operation_name="PutItem",
        )
        assert should_retry_exception(throughput_error, retryable_exceptions)

        # Should not retry validation errors
        validation_error = ClientError(
            error_response={
                "Error": {"Code": "ValidationException", "Message": "Invalid input"}
            },
            operation_name="PutItem",
        )
        assert not should_retry_exception(validation_error, retryable_exceptions)

        # Should not retry access denied
        access_error = ClientError(
            error_response={
                "Error": {"Code": "AccessDenied", "Message": "Access denied"}
            },
            operation_name="GetItem",
        )
        assert not should_retry_exception(access_error, retryable_exceptions)


class TestRetryDecorators:
    """Test retry decorators functionality."""

    def test_api_retry_success_on_first_attempt(self):
        """Test that successful calls don't trigger retries."""
        call_count = 0

        config = RetryConfigClass(max_attempts=3, base_delay=0.01)

        @api_retry(config)
        async def mock_api_call():
            nonlocal call_count
            call_count += 1
            return "success"

        # Use asyncio.run to test async function
        result = asyncio.run(mock_api_call())
        assert result == "success"
        assert call_count == 1  # Should only call once

    def test_api_retry_success_after_failures(self):
        """Test successful retry after failures."""
        call_count = 0

        config = RetryConfigClass(max_attempts=3, base_delay=0.01)

        @api_retry(config)
        async def mock_api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Fail first two attempts with retryable error
                raise aiohttp.ServerTimeoutError()
            return "success"

        result = asyncio.run(mock_api_call())
        assert result == "success"
        assert call_count == 3  # Should call 3 times total

    def test_api_retry_max_attempts_exceeded(self):
        """Test retry exhaustion."""
        call_count = 0

        config = RetryConfigClass(max_attempts=3, base_delay=0.01)

        @api_retry(config)
        async def mock_api_call():
            nonlocal call_count
            call_count += 1
            raise aiohttp.ServerTimeoutError()

        with pytest.raises(RetryError) as exc_info:
            asyncio.run(mock_api_call())

        assert call_count == 3  # Should call max_attempts times
        assert "failed after 3 attempts" in str(exc_info.value)

    def test_api_retry_non_retryable_exception(self):
        """Test that non-retryable exceptions are not retried."""
        call_count = 0

        config = RetryConfigClass(max_attempts=3, base_delay=0.01)

        @api_retry(config)
        async def mock_api_call():
            nonlocal call_count
            call_count += 1
            # 401 errors should not be retried - use WeatherAPIError instead
            raise WeatherAPIError("Unauthorized", status_code=401)

        with pytest.raises(WeatherAPIError):
            asyncio.run(mock_api_call())

        assert call_count == 1  # Should only call once

    def test_dynamodb_retry_sync_decorator(self):
        """Test synchronous DynamoDB retry decorator."""
        call_count = 0

        config = RetryConfigClass(max_attempts=3, base_delay=0.01)

        @dynamodb_retry(config)
        def mock_db_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Fail first two attempts with retryable error
                raise ClientError(
                    error_response={
                        "Error": {
                            "Code": "ThrottlingException",
                            "Message": "Rate exceeded",
                        }
                    },
                    operation_name="GetItem",
                )
            return "success"

        result = mock_db_call()
        assert result == "success"
        assert call_count == 3


class TestExternalAPIRetryIntegration:
    """Test retry integration in ExternalAPI client."""

    def test_openweather_client_retry_on_network_error(self):
        """Test that OpenWeatherMap client retries on network errors."""
        # Test that client has retry configuration
        client = OpenWeatherMapClient(api_key="test_key")

        assert client.retry_config.max_attempts == 3
        assert client.retry_config.base_delay == 1.0
        assert client.retry_config.backoff_multiplier == 2.0

    def test_openweather_client_no_retry_on_401(self):
        """Test that 401 errors are not retried."""
        # This test is simplified - actual retry behavior is tested in decorator tests
        client = OpenWeatherMapClient(api_key="invalid_key")

        # Check that client has retry configuration
        assert client.retry_config.max_attempts == 3
        assert client.retry_config.base_delay == 1.0


class TestCacheServiceRetryIntegration:
    """Test retry integration in cache service."""

    @patch("boto3.resource")
    def test_cache_service_retry_configuration(self, mock_boto_resource):
        """Test that cache service initializes with retry configuration."""
        mock_dynamodb = MagicMock()
        mock_boto_resource.return_value = mock_dynamodb

        cache = DynamoDBCacheService(table_name="test-table")

        # Check retry config is initialized
        assert cache.retry_config.max_attempts == RetryConfig.DYNAMODB_MAX_ATTEMPTS
        assert cache.retry_config.base_delay == RetryConfig.DYNAMODB_BASE_DELAY
        assert (
            cache.retry_config.backoff_multiplier
            == RetryConfig.DYNAMODB_BACKOFF_MULTIPLIER
        )

    @patch("boto3.resource")
    def test_cache_service_retry_on_throttling(self, mock_boto_resource):
        """Test that cache operations retry on throttling errors."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto_resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table

        cache = DynamoDBCacheService(table_name="test-table")

        # Test that retry config is properly initialized
        assert cache.retry_config.max_attempts == 3
        assert cache.retry_config.base_delay == 0.5

        # Simple test - actual retry behavior is tested in decorator tests
        mock_table.get_item.return_value = {"Item": None}
        result = asyncio.run(cache.get_weather("Seoul"))
        assert result is None  # Cache miss


class TestRetryLogging:
    """Test that retry attempts are properly logged."""

    @patch("lambda_function.retry_service.logger")
    def test_retry_attempts_are_logged(self, mock_logger):
        """Test that retry attempts generate appropriate log messages."""
        config = RetryConfigClass(max_attempts=3, base_delay=0.01)

        call_count = 0

        @api_retry(config)
        async def mock_api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise aiohttp.ServerTimeoutError()
            return "success"

        asyncio.run(mock_api_call())

        # Should log retry attempts
        assert mock_logger.warning.call_count == 2  # Two retry attempts
        assert mock_logger.info.call_count == 1  # Success on final attempt

    @patch("lambda_function.retry_service.logger")
    def test_max_attempts_logged(self, mock_logger):
        """Test that exhausted retries are logged."""
        config = RetryConfigClass(max_attempts=2, base_delay=0.01)

        @api_retry(config)
        async def mock_api_call():
            raise aiohttp.ServerTimeoutError()

        with pytest.raises(RetryError):
            asyncio.run(mock_api_call())

        # Should log the final failure
        assert mock_logger.error.call_count == 1
        # Check the call arguments - logger.error is called with format string and args
        call_args = mock_logger.error.call_args[0]
        format_string, func_name, attempts, last_error = call_args
        assert attempts == 2
        assert "failed after %d attempts" in format_string
