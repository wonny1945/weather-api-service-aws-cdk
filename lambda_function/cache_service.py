"""
DynamoDB cache service for weather data.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from models import WeatherResponse

logger = logging.getLogger(__name__)


class CacheError(Exception):
    """Base exception for cache-related errors."""


class DynamoDBCacheService:
    """
    DynamoDB-based caching service for weather data.

    Implements TTL-based caching with automatic expiration.
    """

    def __init__(
        self,
        table_name: Optional[str] = None,
        ttl_minutes: int = 10,
        region: str = "ap-northeast-2",  # Seoul region
    ):
        """
        Initialize DynamoDB cache service.

        Args:
            table_name: DynamoDB table name (defaults to environment variable)
            ttl_minutes: Cache TTL in minutes
            region: AWS region (default: ap-northeast-2 for Seoul)
        """
        self.table_name = table_name or os.getenv("DYNAMODB_TABLE_NAME")
        self.ttl_minutes = ttl_minutes
        self.region = region

        if not self.table_name:
            raise CacheError("DynamoDB table name not provided")

        try:
            # Initialize DynamoDB resource
            self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self.table = self.dynamodb.Table(self.table_name)

            logger.info(
                "Initialized DynamoDB cache service for table: %s in %s",
                self.table_name,
                self.region,
            )
        except (NoCredentialsError, ClientError) as e:
            logger.error("Failed to initialize DynamoDB: %s", e)
            raise CacheError(f"DynamoDB initialization failed: {e}") from e

    def _generate_cache_key(self, city: str) -> str:
        """
        Generate cache key for a city.

        Args:
            city: City name

        Returns:
            Cache key in format: WEATHER#{city}
        """
        # Normalize city name (remove extra spaces, convert to title case)
        normalized_city = city.strip().title()
        return f"WEATHER#{normalized_city}"

    def _generate_expires_at(self) -> int:
        """
        Generate TTL expiration timestamp.

        Returns:
            Unix timestamp when cache entry should expire
        """
        expires_time = datetime.utcnow() + timedelta(minutes=self.ttl_minutes)
        return int(expires_time.timestamp())

    def _is_cache_valid(self, item: Dict) -> bool:
        """
        Check if cache item is still valid.

        Args:
            item: DynamoDB item

        Returns:
            True if cache is valid, False if expired
        """
        if not item:
            return False

        expires_at = item.get("expires_at", 0)
        current_time = int(datetime.utcnow().timestamp())

        return current_time < expires_at

    async def get_weather(self, city: str) -> Optional[WeatherResponse]:
        """
        Get weather data from cache.

        Args:
            city: City name

        Returns:
            WeatherResponse if found and valid, None otherwise
        """
        try:
            cache_key = self._generate_cache_key(city)

            response = self.table.get_item(Key={"PK": cache_key, "SK": "DATA"})

            if "Item" in response:
                item = response["Item"]

                # Check if cache is still valid
                if self._is_cache_valid(item):
                    logger.debug("Cache hit for %s", city)
                    return WeatherResponse(
                        city=item["city"],
                        temperature=float(item["temperature"]),
                        description=item["description"],
                        humidity=int(item["humidity"]),
                        timestamp=item["timestamp"],
                    )
                logger.debug("Cache expired for %s", city)
                return None
            logger.debug("Cache miss for %s", city)
            return None

        except ClientError as e:
            logger.error("DynamoDB error getting cache for %s: %s", city, e)
            # Don't raise exception - gracefully degrade to no cache
            return None
        except (ValueError, TypeError, KeyError) as e:
            logger.error("Unexpected error getting cache for %s: %s", city, e)
            return None

    async def set_weather(self, weather_data: WeatherResponse) -> bool:
        """
        Store weather data in cache.

        Args:
            weather_data: Weather data to cache

        Returns:
            True if successful, False otherwise
        """
        try:
            cache_key = self._generate_cache_key(weather_data.city)
            expires_at = self._generate_expires_at()

            self.table.put_item(
                Item={
                    "PK": cache_key,
                    "SK": "DATA",
                    "city": weather_data.city,
                    "temperature": Decimal(str(weather_data.temperature)),
                    "description": weather_data.description,
                    "humidity": weather_data.humidity,
                    "timestamp": weather_data.timestamp,
                    "expires_at": expires_at,
                    "created_at": datetime.utcnow().isoformat(),
                }
            )

            logger.debug("Cached weather data for %s", weather_data.city)
            return True

        except ClientError as e:
            logger.error(
                "DynamoDB error caching weather for %s: %s", weather_data.city, e
            )
            return False
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(
                "Unexpected error caching weather for %s: %s", weather_data.city, e
            )
            return False

    async def batch_get_weather(self, cities: List[str]) -> Dict[str, WeatherResponse]:
        """
        Get weather data for multiple cities from cache.

        Args:
            cities: List of city names

        Returns:
            Dictionary mapping city names to WeatherResponse objects
        """
        if not cities:
            return {}

        try:
            # Prepare batch get request (limit to 100 items per DynamoDB constraints)
            cache_keys = [
                {"PK": self._generate_cache_key(city), "SK": "DATA"}
                for city in cities[:100]
            ]

            response = self.dynamodb.batch_get_item(
                RequestItems={self.table_name: {"Keys": cache_keys}}
            )

            cached_weather = {}
            for item in response.get("Responses", {}).get(self.table_name, []):
                if self._is_cache_valid(item):
                    city_name = item["city"]
                    cached_weather[city_name] = WeatherResponse(
                        city=city_name,
                        temperature=float(item["temperature"]),
                        description=item["description"],
                        humidity=int(item["humidity"]),
                        timestamp=item["timestamp"],
                    )

            logger.debug(
                "Batch cache hit for %d out of %d cities",
                len(cached_weather),
                len(cities),
            )
            return cached_weather

        except ClientError as e:
            logger.error("DynamoDB error in batch get: %s", e)
            return {}
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error("Unexpected error in batch get: %s", e)
            return {}

    async def batch_set_weather(self, weather_data_list: List[WeatherResponse]) -> int:
        """
        Store multiple weather data entries in cache.

        Args:
            weather_data_list: List of weather data to cache

        Returns:
            Number of items successfully cached
        """
        if not weather_data_list:
            return 0

        try:
            # Prepare batch write request (limit to 25 items per DynamoDB constraints)
            batch_items = []
            expires_at = self._generate_expires_at()

            for weather_data in weather_data_list[:25]:
                cache_key = self._generate_cache_key(weather_data.city)

                batch_items.append(
                    {
                        "PutRequest": {
                            "Item": {
                                "PK": cache_key,
                                "SK": "DATA",
                                "city": weather_data.city,
                                "temperature": Decimal(str(weather_data.temperature)),
                                "description": weather_data.description,
                                "humidity": weather_data.humidity,
                                "timestamp": weather_data.timestamp,
                                "expires_at": expires_at,
                                "created_at": datetime.utcnow().isoformat(),
                            }
                        }
                    }
                )

            # Execute batch write
            self.dynamodb.batch_write_item(RequestItems={self.table_name: batch_items})

            logger.debug("Batch cached %d weather entries", len(batch_items))
            return len(batch_items)

        except ClientError as e:
            logger.error("DynamoDB error in batch set: %s", e)
            return 0
        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Unexpected error in batch set: %s", e)
            return 0

    async def health_check(self) -> bool:
        """
        Check if cache service is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Simple describe table operation to test connectivity
            self.table.meta.client.describe_table(TableName=self.table_name)
            logger.debug("Cache health check passed")
            return True
        except ClientError as e:
            logger.error("Cache health check failed: %s", e)
            return False
        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Unexpected error in cache health check: %s", e)
            return False

    def get_cache_stats(self) -> Dict[str, any]:
        """
        Get cache statistics (for monitoring/debugging).

        Returns:
            Dictionary with cache statistics
        """
        try:
            table_info = self.table.meta.client.describe_table(
                TableName=self.table_name
            )

            return {
                "table_name": self.table_name,
                "table_status": table_info["Table"]["TableStatus"],
                "ttl_minutes": self.ttl_minutes,
                "region": self.region,
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error("Error getting cache stats: %s", e)
            return {"error": str(e)}
