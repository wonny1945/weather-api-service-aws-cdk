# -*- coding: utf-8 -*-
"""
Weather API Service DynamoDB CDK Stack

This stack creates the following components:
- DynamoDB table for weather data caching
- TTL configuration for automatic data expiration
- Environment-specific table naming
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
)
from constructs import Construct

from utils.constants import EnvironmentConfig
from utils.prefixes import ResourcePrefixes, Tags


class DynamoDbStack(Stack):
    """DynamoDB stack for Weather API caching"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Load environment configuration
        self.env_name = env_name
        self.config = EnvironmentConfig.get_config(env_name)

        # Generate resource names
        self.table_name = ResourcePrefixes.get_resource_name(
            env_name, ResourcePrefixes.WEATHER_API, "cache"
        )

        # Apply common tags
        self.common_tags = Tags.get_common_tags(env_name, ResourcePrefixes.WEATHER_API)

        # Create DynamoDB table
        self.weather_cache_table = self._create_weather_cache_table()

        # Apply tags to stack
        self._apply_tags()

    def _create_weather_cache_table(self) -> dynamodb.Table:
        """Create DynamoDB table for weather data caching"""

        table = dynamodb.Table(
            self,
            "WeatherCacheTable",
            table_name=self.table_name,
            # Primary key configuration
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            # TTL configuration for automatic cache expiration
            time_to_live_attribute="expires_at",
            # Billing mode - PAY_PER_REQUEST for all environments
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Encryption configuration
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            # Backup configuration
            point_in_time_recovery=True if self.env_name == "prod" else False,
            # Deletion protection for production
            deletion_protection=True if self.env_name == "prod" else False,
            # Removal policy based on environment
            removal_policy=(
                cdk.RemovalPolicy.RETAIN
                if self.env_name == "prod"
                else cdk.RemovalPolicy.DESTROY
            ),
        )

        return table

    def _apply_tags(self) -> None:
        """Apply common tags to the stack"""
        for key, value in self.common_tags.items():
            cdk.Tags.of(self).add(key, value)

        # Add specific tags for DynamoDB
        cdk.Tags.of(self).add("Component", "Cache")
        cdk.Tags.of(self).add("DataType", "WeatherCache")

    @property
    def table_name_output(self) -> str:
        """Return DynamoDB table name"""
        return self.weather_cache_table.table_name

    @property
    def table_arn(self) -> str:
        """Return DynamoDB table ARN"""
        return self.weather_cache_table.table_arn
