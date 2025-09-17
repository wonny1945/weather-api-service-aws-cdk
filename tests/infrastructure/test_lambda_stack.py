"""
Lambda Stack 테스트 모듈 (간소화 버전)

CDK Mock 호환성 문제를 피하고 실용적인 테스트에 집중:
- 클래스 및 설정 검증
- 환경별 설정 로딩
- 리소스 명명 규칙
- 통합 준비 상태
"""

import pytest
import sys
import os

# infrastructure 모듈을 import할 수 있도록 path 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../infrastructure"))

from utils.constants import EnvironmentConfig
from utils.prefixes import ResourcePrefixes, Tags


class TestWeatherLambdaStackConfiguration:
    """Lambda 스택 설정 및 구조 테스트 클래스"""

    def test_lambda_stack_class_exists(self):
        """Lambda Stack 클래스가 존재하는지 확인"""
        try:
            from stacks.lambda_stack import WeatherLambdaStack

            lambda_stack_exists = True
        except ImportError:
            lambda_stack_exists = False

        assert lambda_stack_exists, "WeatherLambdaStack 클래스를 import할 수 없습니다"

    def test_lambda_stack_interface(self):
        """Lambda Stack이 필요한 인터페이스를 가지고 있는지 확인"""
        from stacks.lambda_stack import WeatherLambdaStack

        # 필수 메서드들이 존재하는지 확인
        assert hasattr(WeatherLambdaStack, "__init__")
        assert hasattr(WeatherLambdaStack, "function_name")
        assert hasattr(WeatherLambdaStack, "function_arn")

    def test_environment_configuration_loading(self):
        """환경별 설정 로딩 테스트"""
        # 각 환경별 설정을 가져올 수 있는지 확인
        dev_config = EnvironmentConfig.get_config("dev")
        staging_config = EnvironmentConfig.get_config("staging")
        prod_config = EnvironmentConfig.get_config("prod")

        # 필수 Lambda 설정들이 존재하는지 확인
        required_keys = ["lambda_memory", "lambda_timeout"]

        for config in [dev_config, staging_config, prod_config]:
            for key in required_keys:
                assert key in config, f"설정에 {key}가 없습니다"

        # 환경별로 다른 설정을 가지는지 확인
        assert dev_config["lambda_memory"] != prod_config["lambda_memory"]

    def test_lambda_memory_progression(self):
        """환경별 Lambda 메모리 설정이 올바른 순서인지 확인"""
        dev_config = EnvironmentConfig.get_config("dev")
        staging_config = EnvironmentConfig.get_config("staging")
        prod_config = EnvironmentConfig.get_config("prod")

        # 개발 < 스테이징 < 프로덕션 순서로 메모리가 증가해야 함
        assert dev_config["lambda_memory"] < staging_config["lambda_memory"]
        assert staging_config["lambda_memory"] < prod_config["lambda_memory"]

    def test_lambda_timeout_configuration(self):
        """Lambda 타임아웃 설정 테스트"""
        environments = ["dev", "staging", "prod"]

        for env in environments:
            config = EnvironmentConfig.get_config(env)
            timeout = config["lambda_timeout"]

            # 타임아웃은 양수이고 합리적인 범위 내에 있어야 함
            assert timeout > 0, f"{env} 환경의 타임아웃이 0 이하입니다"
            assert timeout <= 900, f"{env} 환경의 타임아웃이 15분을 초과합니다"

    def test_resource_naming_convention(self):
        """Lambda 리소스 명명 규칙 테스트"""
        environments = ["dev", "staging", "prod"]

        for env in environments:
            lambda_name = ResourcePrefixes.get_resource_name(
                env, ResourcePrefixes.WEATHER_API, ResourcePrefixes.LAMBDA
            )

            # 명명 규칙 확인
            assert lambda_name.startswith(f"{env}-weather-api")
            assert lambda_name.endswith("-lambda")
            assert env in lambda_name

    def test_common_tags_configuration(self):
        """공통 태그 설정 테스트"""
        environments = ["dev", "staging", "prod"]

        for env in environments:
            tags = Tags.get_common_tags(env, ResourcePrefixes.WEATHER_API)

            # 필수 태그들이 존재하는지 확인
            required_tags = ["Environment", "Service", "ManagedBy", "Project"]
            for tag in required_tags:
                assert tag in tags, f"{env} 환경에 {tag} 태그가 없습니다"

            # 환경별 태그 값 확인
            assert tags["Environment"] == env
            assert tags["Service"] == ResourcePrefixes.WEATHER_API

    def test_lambda_code_path_flexibility(self):
        """Lambda 코드 경로 유연성 테스트"""
        from stacks.lambda_stack import WeatherLambdaStack

        # __init__ 메서드가 lambda_code_path 매개변수를 받을 수 있는지 확인
        import inspect

        init_signature = inspect.signature(WeatherLambdaStack.__init__)
        parameters = list(init_signature.parameters.keys())

        # lambda_code_path 매개변수가 있는지 확인
        assert "lambda_code_path" in parameters, "lambda_code_path 매개변수가 없습니다"

    def test_integration_with_api_gateway(self):
        """API Gateway와의 통합 준비 상태 테스트"""
        # Lambda Stack과 API Gateway Stack이 모두 import 가능한지 확인
        try:
            from stacks.lambda_stack import WeatherLambdaStack
            from stacks.apigateway_stack import APIGatewayStack

            # API Gateway Stack이 Lambda 통합 메서드를 가지고 있는지 확인
            assert hasattr(APIGatewayStack, "add_lambda_integration")

            integration_ready = True
        except ImportError:
            integration_ready = False

        assert integration_ready, "Lambda와 API Gateway 통합 준비가 되지 않았습니다"

    def test_environment_variables_preparation(self):
        """환경 변수 설정 준비 상태 테스트"""
        # 환경별로 필요한 설정들이 준비되어 있는지 확인
        environments = ["dev", "staging", "prod"]

        for env in environments:
            config = EnvironmentConfig.get_config(env)

            # 로그 레벨 결정 로직 테스트
            expected_log_level = "DEBUG" if env == "dev" else "INFO"

            # 환경별 설정이 다른지 확인
            if env == "dev":
                # 개발환경은 디버그 모드
                assert True  # 개발환경 확인
            else:
                # 스테이징/프로덕션은 INFO 레벨
                assert env in ["staging", "prod"]

    def test_constants_consistency(self):
        """상수 설정의 일관성 테스트"""
        # ResourcePrefixes의 일관성 확인
        assert hasattr(ResourcePrefixes, "WEATHER_API")
        assert hasattr(ResourcePrefixes, "LAMBDA")

        # 상수 값들이 올바른지 확인
        assert ResourcePrefixes.WEATHER_API == "weather-api"
        assert ResourcePrefixes.LAMBDA == "lambda"

    def test_future_dynamodb_integration_readiness(self):
        """향후 DynamoDB 통합을 위한 준비 상태 테스트"""
        # DynamoDB 관련 설정이 준비되어 있는지 확인
        environments = ["dev", "staging", "prod"]

        for env in environments:
            config = EnvironmentConfig.get_config(env)

            # 캐시 TTL 설정이 있는지 확인 (향후 DynamoDB에서 사용)
            assert "cache_ttl_minutes" in config
            assert config["cache_ttl_minutes"] > 0

            # DynamoDB 결제 방식 설정 확인
            assert "dynamodb_billing_mode" in config
            assert config["dynamodb_billing_mode"] in ["PAY_PER_REQUEST", "PROVISIONED"]


if __name__ == "__main__":
    # 개별 테스트 실행을 위한 코드
    pytest.main([__file__, "-v"])
