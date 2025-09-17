#!/usr/bin/env python3

import os
import argparse
import boto3
from botocore.exceptions import NoCredentialsError, ProfileNotFound

import aws_cdk as cdk
from utils.prefixes import ResourcePrefixes
from stacks.apigateway_stack import APIGatewayStack


def get_aws_account_and_region():
    """AWS config에서 계정과 리전 정보를 자동 감지"""
    try:
        session = boto3.Session()

        # STS를 사용해서 계정 ID 가져오기
        sts_client = session.client("sts")
        account = sts_client.get_caller_identity()["Account"]

        # 현재 세션의 리전 가져오기
        region = session.region_name

        return account, region
    except (NoCredentialsError, ProfileNotFound) as e:
        print(f"AWS credentials not found: {e}")
        return None, None
    except Exception as e:
        print(f"Error getting AWS config: {e}")
        return None, None


def parse_arguments():
    """명령어 인자 파싱"""
    parser = argparse.ArgumentParser(description="Deploy Weather API CDK Stack")
    parser.add_argument(
        "--env",
        choices=["dev", "staging", "prod"],
        help="Deployment environment (dev, staging, prod)",
    )
    parser.add_argument("--account", help="AWS Account ID (overrides auto-detection)")
    parser.add_argument("--region", help="AWS Region (overrides auto-detection)")

    return parser.parse_args()


def main():
    # 명령어 인자 파싱
    args = parse_arguments()

    app = cdk.App()

    # 환경 결정 (우선순위: 명령어 인자 > CDK context > 기본값)
    env = args.env or app.node.try_get_context("env") or "dev"

    # AWS 계정/리전 정보 가져오기
    account, region = get_aws_account_and_region()

    # 명령어 인자로 오버라이드 가능
    if args.account:
        account = args.account
    if args.region:
        region = args.region

    # 환경변수로 fallback
    if not account:
        account = os.getenv("CDK_DEFAULT_ACCOUNT")
    if not region:
        region = os.getenv("CDK_DEFAULT_REGION")

    print(f"Deploying to environment: {env}")
    print(f"AWS Account: {account}")
    print(f"AWS Region: {region}")

    # CDK 환경 설정
    cdk_env = cdk.Environment(account=account, region=region)

    # API Gateway 스택 생성
    stack_name = ResourcePrefixes.get_stack_name(env, ResourcePrefixes.WEATHER_API)
    api_gateway_stack = APIGatewayStack(
        app,
        stack_name,
        env_name=env,
        env=cdk_env,
        description=f"Weather API Gateway Stack for {env} environment"
    )

    print(f"Created stack: {stack_name}")

    app.synth()


if __name__ == "__main__":
    main()
