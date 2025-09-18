# -*- coding: utf-8 -*-
"""
Weather API Service API Gateway CDK Stack

This stack creates the following components:
- REST API Gateway with environment-specific CORS settings
- Environment-specific throttling settings
- Weather API endpoints (/weather/{city}, /weather/batch, /health)
- Lambda function integration ready (add_lambda_integration method provided)
"""

from typing import Optional
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_logs as logs,
)
from constructs import Construct

from utils.constants import EnvironmentConfig, APIEndpoints, CORSConfig
from utils.prefixes import ResourcePrefixes, Tags


class APIGatewayStack(Stack):
    """API Gateway stack for Weather API service"""

    def __init__(
        self, scope: Construct, construct_id: str, env_name: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Load environment configuration
        self.env_name = env_name
        self.config = EnvironmentConfig.get_config(env_name)

        # Generate resource names
        self.api_name = ResourcePrefixes.get_resource_name(
            env_name, ResourcePrefixes.WEATHER_API, ResourcePrefixes.API_GW
        )

        # Apply common tags
        self.common_tags = Tags.get_common_tags(env_name, ResourcePrefixes.WEATHER_API)

        # Create API Gateway
        self.api = self._create_api_gateway()

        # Create API endpoint resources (ready for Lambda connection)
        self._create_api_resources()

        # Apply tags to stack
        self._apply_tags()

    def _create_api_gateway(self) -> apigateway.RestApi:
        """Create REST API Gateway with basic configuration"""

        # Get environment-specific allowed CORS origins
        allowed_origins = CORSConfig.get_allowed_origins(self.env_name)

        # CORS configuration
        cors_options = apigateway.CorsOptions(
            allow_origins=allowed_origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=[
                "Content-Type",
                "X-Amz-Date",
                "Authorization",
                "X-Api-Key",
                "X-Amz-Security-Token",
            ],
            allow_credentials=False,
        )

        # Create log group
        log_group = logs.LogGroup(
            self,
            "WeatherAPIAccessLogs",
            log_group_name=f"/aws/apigateway/{self.api_name}",
            retention=(
                logs.RetentionDays.ONE_WEEK
                if self.env_name == "dev"
                else (
                    logs.RetentionDays.TWO_WEEKS
                    if self.env_name == "staging"
                    else logs.RetentionDays.ONE_MONTH
                )
            ),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # Create API Gateway
        api = apigateway.RestApi(
            self,
            "WeatherAPI",
            rest_api_name=self.api_name,
            description=f"Weather API Gateway for {self.env_name} environment",
            deploy_options=apigateway.StageOptions(
                stage_name=self.env_name,
                # Environment-specific throttling settings
                throttling_rate_limit=self.config["api_throttling_rate"],
                throttling_burst_limit=self.config["api_throttling_burst"],
                # Access log settings
                access_log_destination=apigateway.LogGroupLogDestination(
                    log_group=log_group
                ),
                access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
            ),
            default_cors_preflight_options=cors_options,
            cloud_watch_role=True,
        )

        return api

    def _create_api_resources(self) -> None:
        """Create API resource structure (Lambda connection in separate method)"""

        # Create /weather resource
        self.weather_resource = self.api.root.add_resource("weather")

        # GET /weather/{city} - Single city weather query
        self.city_resource = self.weather_resource.add_resource("{city}")

        # POST /weather/batch - Batch city weather query
        self.batch_resource = self.weather_resource.add_resource("batch")

        # GET /health - Health check
        self.health_resource = self.api.root.add_resource("health")

    def add_lambda_integration(
        self,
        lambda_function: lambda_.Function,
        paths: list = None,
        methods: list = None,
    ) -> None:
        """
        Connect Lambda function to API Gateway endpoints
        This method is called after both stacks are created.
        """

        # Create Lambda integration
        lambda_integration = apigateway.LambdaIntegration(
            lambda_function,
            proxy=True,  # Proxy all requests to Lambda
            allow_test_invoke=True,
        )

        # Add Lambda integration to all weather API endpoints
        self.city_resource.add_method("GET", lambda_integration)
        self.batch_resource.add_method("POST", lambda_integration)
        self.health_resource.add_method("GET", lambda_integration)

        # Note: LambdaIntegration automatically grants necessary permissions
        # Manual add_permission is not required and causes circular dependency

    def _apply_tags(self) -> None:
        """Apply common tags to the stack"""
        for key, value in self.common_tags.items():
            cdk.Tags.of(self).add(key, value)

    @property
    def api_url(self) -> str:
        """Return API Gateway URL"""
        return self.api.url

    @property
    def api_id(self) -> str:
        """Return API Gateway ID"""
        return self.api.rest_api_id

    @property
    def api_arn(self) -> str:
        """Return API Gateway ARN"""
        return self.api.arn_for_execute_api()
