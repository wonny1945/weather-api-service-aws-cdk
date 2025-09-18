# -*- coding: utf-8 -*-
"""
Weather API Service Lambda CDK Stack

This stack creates the following components:
- Lambda function for weather API endpoints (single city and batch processing)
- IAM execution role with necessary permissions
- CloudWatch log group for Lambda function
- X-Ray tracing configuration
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct

from utils.constants import EnvironmentConfig
from utils.prefixes import ResourcePrefixes, Tags


class LambdaStack(Stack):
    """Lambda stack for Weather API service"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        lambda_code_path: str = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Load environment configuration
        self.env_name = env_name
        self.config = EnvironmentConfig.get_config(env_name)
        self.lambda_code_path = lambda_code_path

        # Generate resource names
        self.lambda_name = ResourcePrefixes.get_resource_name(
            env_name, ResourcePrefixes.WEATHER_API, ResourcePrefixes.LAMBDA
        )

        # Apply common tags
        self.common_tags = Tags.get_common_tags(env_name, ResourcePrefixes.WEATHER_API)

        # Create IAM execution role
        self.lambda_role = self._create_lambda_role()

        # Create CloudWatch log group
        self.log_group = self._create_log_group()

        # Create Lambda function
        self.lambda_function = self._create_lambda_function()

        # Apply tags to stack
        self._apply_tags()

    def _create_lambda_role(self) -> iam.Role:
        """Create IAM execution role for Lambda function"""

        role = iam.Role(
            self,
            "WeatherLambdaRole",
            role_name=f"{self.lambda_name}-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description=f"Execution role for Weather API Lambda function ({self.env_name})",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Add X-Ray tracing permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
                resources=["*"],
            )
        )

        # TODO: Add DynamoDB permissions when caching is implemented
        # role.add_to_policy(
        #     iam.PolicyStatement(
        #         effect=iam.Effect.ALLOW,
        #         actions=[
        #             "dynamodb:GetItem",
        #             "dynamodb:PutItem",
        #             "dynamodb:UpdateItem",
        #             "dynamodb:DeleteItem"
        #         ],
        #         resources=[dynamodb_table_arn]
        #     )
        # )

        return role

    def _create_log_group(self) -> logs.LogGroup:
        """Create CloudWatch log group for Lambda function"""

        log_group = logs.LogGroup(
            self,
            "WeatherLambdaLogGroup",
            log_group_name=f"/aws/lambda/{self.lambda_name}",
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

        return log_group

    def _create_lambda_function(self) -> lambda_.Function:
        """Create Lambda function"""

        # Use provided code path or default asset location
        asset_path = self.lambda_code_path

        code = lambda_.Code.from_asset(
            asset_path,
            bundling=lambda_.BundlingOptions(
                image=lambda_.Runtime.PYTHON_3_11.bundling_image,
                command=[
                    "bash",
                    "-c",
                    "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output",
                ],
            ),
        )

        lambda_function = lambda_.Function(
            self,
            "WeatherLambdaFunction",
            function_name=self.lambda_name,
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=code,
            role=self.lambda_role,
            # Environment-specific configuration
            memory_size=self.config["lambda_memory"],
            timeout=cdk.Duration.seconds(self.config["lambda_timeout"]),
            # Environment variables
            environment={
                "ENV": self.env_name,
                "LOG_LEVEL": "DEBUG" if self.env_name == "dev" else "INFO",
                # TODO: Add these when implementing actual functionality
                # "CACHE_TTL_MINUTES": str(self.config["cache_ttl_minutes"]),
                # "DYNAMODB_TABLE_NAME": dynamodb_table_name
            },
            # Enable X-Ray tracing
            tracing=lambda_.Tracing.ACTIVE,
            # Associate with log group
            log_group=self.log_group,
            description=f"Weather API Lambda function for {self.env_name} environment",
        )

        return lambda_function

    def _apply_tags(self) -> None:
        """Apply common tags to the stack"""
        for key, value in self.common_tags.items():
            cdk.Tags.of(self).add(key, value)

    @property
    def function_name(self) -> str:
        """Return Lambda function name"""
        return self.lambda_function.function_name

    @property
    def function_arn(self) -> str:
        """Return Lambda function ARN"""
        return self.lambda_function.function_arn
