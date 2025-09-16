"""
Constants and configuration values for infrastructure
"""

from typing import Dict, Any


class EnvironmentConfig:
    """Environment-specific configuration"""

    DEV = {
        "lambda_memory": 256,
        "lambda_timeout": 30,
        "dynamodb_billing_mode": "PAY_PER_REQUEST",
        "api_throttling_rate": 100,
        "api_throttling_burst": 200,
        "cache_ttl_minutes": 10,
        "log_retention_days": 7,
    }

    STAGING = {
        "lambda_memory": 512,
        "lambda_timeout": 30,
        "dynamodb_billing_mode": "PAY_PER_REQUEST",
        "api_throttling_rate": 500,
        "api_throttling_burst": 1000,
        "cache_ttl_minutes": 10,
        "log_retention_days": 14,
    }

    PROD = {
        "lambda_memory": 1024,
        "lambda_timeout": 30,
        "dynamodb_billing_mode": "PROVISIONED",
        "dynamodb_read_capacity": 10,
        "dynamodb_write_capacity": 5,
        "api_throttling_rate": 1000,
        "api_throttling_burst": 2000,
        "cache_ttl_minutes": 10,
        "log_retention_days": 30,
    }

    @classmethod
    def get_config(cls, env: str) -> Dict[str, Any]:
        """Get configuration for environment"""
        configs = {"dev": cls.DEV, "staging": cls.STAGING, "prod": cls.PROD}
        return configs.get(env, cls.DEV)


class APIEndpoints:
    """API endpoint paths"""

    WEATHER_SINGLE = "/weather/{city}"
    WEATHER_BATCH = "/weather/batch"
    HEALTH_CHECK = "/health"


class ExternalAPIConfig:
    """External API configuration"""

    OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
    OPENWEATHER_TIMEOUT = 10
    RETRY_MAX_ATTEMPTS = 3
    RETRY_BACKOFF_MULTIPLIER = 2
