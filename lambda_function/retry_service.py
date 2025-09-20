"""
Retry service with exponential backoff and jitter for resilient API calls.

This module provides decorators and utilities for implementing retry logic
with exponential backoff and jitter to handle transient failures gracefully.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Tuple, Type

import aiohttp
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""

    def __init__(self, message: str, last_exception: Exception):
        self.message = message
        self.last_exception = last_exception
        super().__init__(message)


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(  # pylint: disable=too-many-arguments,R0917
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        backoff_multiplier: float = 2.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        jitter_range: float = 0.1,
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay in seconds before first retry
            backoff_multiplier: Multiplier for exponential backoff
            max_delay: Maximum delay between retries
            jitter: Whether to apply jitter to reduce thundering herd
            jitter_range: Jitter range as percentage (0.1 = ±10%)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.backoff_multiplier = backoff_multiplier
        self.max_delay = max_delay
        self.jitter = jitter
        self.jitter_range = jitter_range


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate delay with exponential backoff and jitter.

    Args:
        attempt: Current attempt number (1-based)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    # Calculate exponential backoff delay
    delay = config.base_delay * (config.backoff_multiplier ** (attempt - 1))

    # Apply maximum delay limit
    delay = min(delay, config.max_delay)

    # Apply jitter if enabled
    if config.jitter:
        jitter_amount = delay * config.jitter_range
        jitter_offset = random.uniform(-jitter_amount, jitter_amount)
        delay = max(0, delay + jitter_offset)

    return delay


def should_retry_exception(
    exception: Exception, retryable_exceptions: Tuple[Type[Exception], ...]
) -> bool:
    """
    Determine if an exception should trigger a retry.

    Args:
        exception: The exception that occurred
        retryable_exceptions: Tuple of exception types that should be retried

    Returns:
        True if the exception should be retried, False otherwise
    """
    # Check if exception type is retryable
    if not isinstance(exception, retryable_exceptions):
        return False

    # Special handling for aiohttp ClientResponseError
    if isinstance(exception, aiohttp.ClientResponseError):
        # Don't retry client errors (4xx)
        if 400 <= exception.status < 500:
            return False
        # Retry server errors (5xx) and other status codes
        return True

    # Special handling for boto3 ClientError
    if isinstance(exception, ClientError):
        error_code = exception.response.get("Error", {}).get("Code", "")

        # Don't retry client errors
        non_retryable_codes = [
            "AccessDenied",
            "InvalidParameterValue",
            "ValidationException",
            "ResourceNotFound",
            "ItemNotFound",
        ]
        if error_code in non_retryable_codes:
            return False

        # Retry throttling and server errors
        retryable_codes = [
            "ThrottlingException",
            "ProvisionedThroughputExceededException",
            "RequestLimitExceeded",
            "ServiceUnavailable",
            "InternalServerError",
        ]
        return error_code in retryable_codes or error_code.startswith("5")

    return True


def retry_sync(
    config: RetryConfig,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    log_attempts: bool = True,
) -> Callable:
    """
    Decorator for synchronous functions with retry logic.

    Args:
        config: Retry configuration
        retryable_exceptions: Tuple of exception types to retry on
        log_attempts: Whether to log retry attempts

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 1 and log_attempts:
                        logger.info(
                            "Function %s succeeded on attempt %d/%d",
                            func.__name__,
                            attempt,
                            config.max_attempts,
                        )
                    return result

                except Exception as e:  # pylint: disable=broad-exception-caught
                    last_exception = e

                    if not should_retry_exception(e, retryable_exceptions):
                        if log_attempts:
                            logger.warning(
                                "Function %s failed with non-retryable exception: %s",
                                func.__name__,
                                str(e),
                            )
                        raise e

                    if attempt == config.max_attempts:
                        if log_attempts:
                            logger.error(
                                "Function %s failed after %d attempts. Last error: %s",
                                func.__name__,
                                config.max_attempts,
                                str(e),
                            )
                        break

                    delay = calculate_delay(attempt, config)
                    if log_attempts:
                        logger.warning(
                            "Function %s failed on attempt %d/%d: %s. Retrying in %.2f seconds",  # pylint: disable=line-too-long
                            func.__name__,
                            attempt,
                            config.max_attempts,
                            str(e),
                            delay,
                        )

                    time.sleep(delay)

            raise RetryError(
                f"Function {func.__name__} failed after {config.max_attempts} attempts",
                last_exception,
            )

        return wrapper

    return decorator


def retry_async(
    config: RetryConfig,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    log_attempts: bool = True,
) -> Callable:
    """
    Decorator for asynchronous functions with retry logic.

    Args:
        config: Retry configuration
        retryable_exceptions: Tuple of exception types to retry on
        log_attempts: Whether to log retry attempts

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 1 and log_attempts:
                        logger.info(
                            "Function %s succeeded on attempt %d/%d",
                            func.__name__,
                            attempt,
                            config.max_attempts,
                        )
                    return result

                except Exception as e:  # pylint: disable=broad-exception-caught
                    last_exception = e

                    if not should_retry_exception(e, retryable_exceptions):
                        if log_attempts:
                            logger.warning(
                                "Function %s failed with non-retryable exception: %s",
                                func.__name__,
                                str(e),
                            )
                        raise e

                    if attempt == config.max_attempts:
                        if log_attempts:
                            logger.error(
                                "Function %s failed after %d attempts. Last error: %s",
                                func.__name__,
                                config.max_attempts,
                                str(e),
                            )
                        break

                    delay = calculate_delay(attempt, config)
                    if log_attempts:
                        logger.warning(
                            "Function %s failed on attempt %d/%d: %s. Retrying in %.2f seconds",  # pylint: disable=line-too-long
                            func.__name__,
                            attempt,
                            config.max_attempts,
                            str(e),
                            delay,
                        )

                    await asyncio.sleep(delay)

            raise RetryError(
                f"Function {func.__name__} failed after {config.max_attempts} attempts",
                last_exception,
            )

        return wrapper

    return decorator


# Pre-configured retry decorators for common use cases


def api_retry(config: RetryConfig) -> Callable:
    """
    Retry decorator for external API calls.

    Retries on network errors, timeouts, and server errors (5xx).
    Does not retry on client errors (4xx).
    """
    retryable_exceptions = (
        aiohttp.ClientError,
        aiohttp.ServerTimeoutError,
        asyncio.TimeoutError,
        ConnectionError,
    )
    return retry_async(config, retryable_exceptions)


def dynamodb_retry(config: RetryConfig) -> Callable:
    """
    Retry decorator for DynamoDB operations.

    Retries on throttling, provisioned throughput exceeded, and server errors.
    Does not retry on client errors like validation failures.
    """
    retryable_exceptions = (ClientError,)
    return retry_sync(config, retryable_exceptions)


def dynamodb_retry_async(config: RetryConfig) -> Callable:
    """
    Async retry decorator for DynamoDB operations.

    Retries on throttling, provisioned throughput exceeded, and server errors.
    Does not retry on client errors like validation failures.
    """
    retryable_exceptions = (ClientError,)
    return retry_async(config, retryable_exceptions)
