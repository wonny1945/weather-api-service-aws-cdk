"""
Configuration constants for Lambda function.
"""

import os


class RetryConfig:
    """Retry configuration for resilient operations"""

    # API retry configuration
    API_MAX_ATTEMPTS = 3
    API_BASE_DELAY = 1.0
    API_BACKOFF_MULTIPLIER = 2.0
    API_MAX_DELAY = 30.0
    API_JITTER = True
    API_JITTER_RANGE = 0.1

    # DynamoDB retry configuration
    DYNAMODB_MAX_ATTEMPTS = 3
    DYNAMODB_BASE_DELAY = 0.5
    DYNAMODB_BACKOFF_MULTIPLIER = 2.0
    DYNAMODB_MAX_DELAY = 10.0
    DYNAMODB_JITTER = True
    DYNAMODB_JITTER_RANGE = 0.1


class ExternalAPIConfig:
    """External API configuration"""

    OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
    OPENWEATHER_TIMEOUT = 10


class LambdaConfig:
    """Lambda-specific configuration"""

    # Environment variables
    ENV = os.getenv("ENV", "dev")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    CACHE_TTL_MINUTES = int(os.getenv("CACHE_TTL_MINUTES", "10"))
    DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "")

    # API Key (should be retrieved from AWS Systems Manager in production)
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
