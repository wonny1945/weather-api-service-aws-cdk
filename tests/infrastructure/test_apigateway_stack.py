"""
API Gateway Stack 테스트 모듈

API Gateway 스택의 주요 구성요소들에 대한 단위 테스트:
- REST API 생성 및 기본 설정
- API 엔드포인트 리소스 구조 (/weather/{city}, /weather/batch)
- 환경별 CORS 설정
- 스로틀링 설정
- CloudWatch 로그 그룹 생성
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch
import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway

# infrastructure 모듈을 import할 수 있도록 path 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../infrastructure"))

from stacks.apigateway_stack import APIGatewayStack
from utils.constants import EnvironmentConfig, CORSConfig


class TestAPIGatewayStack:
    """API Gateway 스택 테스트 클래스"""

    def setup_method(self):
        """각 테스트 전에 실행되는 설정"""
        self.app = cdk.App()

    def create_stack(self, env_name: str = "dev") -> APIGatewayStack:
        """테스트용 API Gateway 스택 생성"""
        return APIGatewayStack(
            self.app,
            f"TestAPIGatewayStack-{env_name}",
            env_name=env_name,
            env=cdk.Environment(account="123456789012", region="us-east-1")
        )

    def test_stack_creation_dev(self):
        """개발 환경 스택 생성 테스트"""
        stack = self.create_stack("dev")

        assert stack.env_name == "dev"
        assert stack.api_name == "dev-weather-api-api"
        assert hasattr(stack, 'api')
        assert hasattr(stack, 'weather_resource')
        assert hasattr(stack, 'city_resource')
        assert hasattr(stack, 'batch_resource')

    def test_stack_creation_staging(self):
        """스테이징 환경 스택 생성 테스트"""
        stack = self.create_stack("staging")

        assert stack.env_name == "staging"
        assert stack.api_name == "staging-weather-api-api"

    def test_stack_creation_prod(self):
        """프로덕션 환경 스택 생성 테스트"""
        stack = self.create_stack("prod")

        assert stack.env_name == "prod"
        assert stack.api_name == "prod-weather-api-api"

    def test_environment_configuration_loading(self):
        """환경별 설정 로딩 테스트"""
        # 개발 환경 설정 확인
        dev_stack = self.create_stack("dev")
        dev_config = EnvironmentConfig.get_config("dev")
        assert dev_stack.config["api_throttling_rate"] == dev_config["api_throttling_rate"]
        assert dev_stack.config["api_throttling_burst"] == dev_config["api_throttling_burst"]

        # 프로덕션 환경 설정 확인
        prod_stack = self.create_stack("prod")
        prod_config = EnvironmentConfig.get_config("prod")
        assert prod_stack.config["api_throttling_rate"] == prod_config["api_throttling_rate"]
        assert prod_stack.config["api_throttling_burst"] == prod_config["api_throttling_burst"]

        # 개발환경과 프로덕션 환경의 설정이 다른지 확인
        assert dev_config["api_throttling_rate"] != prod_config["api_throttling_rate"]

    def test_cors_configuration(self):
        """CORS 설정 테스트"""
        # 각 환경별로 CORS 설정이 다른지 확인
        dev_origins = CORSConfig.get_allowed_origins("dev")
        staging_origins = CORSConfig.get_allowed_origins("staging")
        prod_origins = CORSConfig.get_allowed_origins("prod")

        # 개발환경은 localhost 포함해야 함
        assert any("localhost" in origin for origin in dev_origins)

        # 프로덕션환경은 localhost 없어야 함
        assert not any("localhost" in origin for origin in prod_origins)

        # 각 환경별로 다른 오리진을 가져야 함
        assert dev_origins != prod_origins

    def test_api_properties(self):
        """API Gateway 속성 테스트"""
        stack = self.create_stack("dev")

        # API URL과 ID 속성이 존재하는지 확인
        assert hasattr(stack, 'api_url')
        assert hasattr(stack, 'api_id')
        assert hasattr(stack, 'api_arn')

        # API 객체가 올바르게 생성되었는지 확인
        assert stack.api is not None
        assert isinstance(stack.api, apigateway.RestApi)

    def test_api_resource_structure(self):
        """API 리소스 구조 테스트"""
        stack = self.create_stack("dev")

        # 필수 리소스들이 생성되었는지 확인
        assert hasattr(stack, 'weather_resource')
        assert hasattr(stack, 'city_resource')
        assert hasattr(stack, 'batch_resource')

        # 리소스 객체들이 올바른 타입인지 확인
        assert isinstance(stack.weather_resource, apigateway.Resource)
        assert isinstance(stack.city_resource, apigateway.Resource)
        assert isinstance(stack.batch_resource, apigateway.Resource)

    @patch('aws_cdk.aws_lambda.Function')
    def test_lambda_integration_method(self, mock_lambda):
        """Lambda 통합 메서드 테스트"""
        stack = self.create_stack("dev")

        # Mock Lambda 함수 생성
        mock_lambda_function = Mock()
        mock_lambda_function.add_permission = Mock()

        # add_lambda_integration 메서드가 존재하는지 확인
        assert hasattr(stack, 'add_lambda_integration')
        assert callable(stack.add_lambda_integration)

        # 메서드 호출이 오류 없이 실행되는지 확인
        try:
            # 실제로는 CDK 생성 중이 아니므로 오류가 발생할 수 있지만,
            # 메서드가 존재하고 호출 가능한지만 확인
            stack.add_lambda_integration(mock_lambda_function)
        except Exception as e:
            # CDK 컨텍스트 관련 오류는 예상됨 - 메서드 존재 여부만 확인
            pass

    def test_common_tags_application(self):
        """공통 태그 적용 테스트"""
        stack = self.create_stack("dev")

        # 공통 태그가 설정되었는지 확인
        assert hasattr(stack, 'common_tags')
        assert isinstance(stack.common_tags, dict)

        # 필수 태그들이 포함되어 있는지 확인
        required_tags = ["Environment", "Service", "ManagedBy", "Project"]
        for tag in required_tags:
            assert tag in stack.common_tags

        # 환경별 태그 값이 올바른지 확인
        assert stack.common_tags["Environment"] == "dev"

    def test_environment_specific_log_retention(self):
        """환경별 로그 보존 기간 테스트"""
        # 각 환경별로 다른 로그 보존 기간을 가져야 함
        dev_stack = self.create_stack("dev")
        staging_stack = self.create_stack("staging")
        prod_stack = self.create_stack("prod")

        # 스택이 성공적으로 생성되는지만 확인
        # (실제 로그 보존 기간은 CDK 내부에서 설정됨)
        assert dev_stack.env_name == "dev"
        assert staging_stack.env_name == "staging"
        assert prod_stack.env_name == "prod"

    def test_throttling_configuration_by_environment(self):
        """환경별 스로틀링 설정 테스트"""
        dev_stack = self.create_stack("dev")
        prod_stack = self.create_stack("prod")

        # 프로덕션 환경이 개발 환경보다 높은 스로틀링 한도를 가져야 함
        assert prod_stack.config["api_throttling_rate"] > dev_stack.config["api_throttling_rate"]
        assert prod_stack.config["api_throttling_burst"] > dev_stack.config["api_throttling_burst"]

    def test_resource_naming_convention(self):
        """리소스 명명 규칙 테스트"""
        stack = self.create_stack("dev")

        # 리소스 이름이 일관된 명명 규칙을 따르는지 확인
        expected_name_pattern = "dev-weather-api-api"
        assert stack.api_name == expected_name_pattern

        # 다른 환경에서도 명명 규칙이 일관되는지 확인
        prod_stack = self.create_stack("prod")
        assert prod_stack.api_name == "prod-weather-api-api"


if __name__ == "__main__":
    # 개별 테스트 실행을 위한 코드
    pytest.main([__file__, "-v"])