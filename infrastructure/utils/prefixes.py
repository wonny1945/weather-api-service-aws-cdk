"""
Prefix and naming utilities for AWS resources
"""


class ResourcePrefixes:
    """Standard prefixes for AWS resources"""

    # Environment prefixes
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"

    # Service prefixes
    WEATHER_API = "weather-api"

    # Resource type prefixes
    LAMBDA = "lambda"
    API_GW = "api"

    @classmethod
    def get_resource_name(
        cls, env: str, service: str, resource_type: str, name: str = ""
    ) -> str:
        """Generate standardized resource name"""
        parts = [env, service, resource_type]
        if name:
            parts.append(name)
        return "-".join(parts)


class Tags:
    """Standard tags for AWS resources"""

    @classmethod
    def get_common_tags(cls, env: str, service: str = "weather-api") -> dict:
        """Get common tags for all resources"""
        return {
            "Environment": env,
            "Service": service,
            "ManagedBy": "CDK",
            "Project": "weather-api-service",
        }
