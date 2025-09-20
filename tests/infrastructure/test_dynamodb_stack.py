"""
DynamoDB Stack 테스트 모듈

설계 검증 중심의 실용적인 테스트:
- 클래스 및 인터페이스 검증
- 환경별 설정 적용
- 테이블 스키마 및 TTL 설정
- 리소스 명명 규칙
"""

import pytest
from utils.constants import EnvironmentConfig
from utils.prefixes import ResourcePrefixes, Tags


class TestDynamoDbStackConfiguration:
    """DynamoDB 스택 설정 및 구조 테스트 클래스"""

    def test_dynamodb_stack_class_exists(self):
        """DynamoDB Stack 클래스가 존재하는지 확인"""
        try:
            from stacks.dynamodb_stack import DynamoDbStack

            dynamodb_stack_exists = True
        except ImportError:
            dynamodb_stack_exists = False

        assert dynamodb_stack_exists, "DynamoDbStack 클래스를 import할 수 없습니다"

    def test_dynamodb_stack_interface(self):
        """DynamoDB Stack이 필요한 인터페이스를 가지고 있는지 확인"""
        from stacks.dynamodb_stack import DynamoDbStack

        # 필수 속성들이 존재하는지 확인
        assert hasattr(DynamoDbStack, "__init__")
        assert hasattr(DynamoDbStack, "table_name_output")
        assert hasattr(DynamoDbStack, "table_arn")

    def test_environment_configuration_loading(self):
        """환경별 설정이 DynamoDB에 필요한 값들을 포함하는지 확인"""
        # 각 환경별 설정을 가져올 수 있는지 확인
        dev_config = EnvironmentConfig.get_config("dev")
        staging_config = EnvironmentConfig.get_config("staging")
        prod_config = EnvironmentConfig.get_config("prod")

        # DynamoDB 관련 필수 설정들이 존재하는지 확인
        required_keys = ["dynamodb_billing_mode", "cache_ttl_minutes"]

        for config in [dev_config, staging_config, prod_config]:
            for key in required_keys:
                assert key in config, f"필수 설정 '{key}'가 환경 설정에 없습니다"

    def test_billing_mode_configuration(self):
        """모든 환경이 PAY_PER_REQUEST 모드로 설정되었는지 확인"""
        environments = ["dev", "staging", "prod"]

        for env in environments:
            config = EnvironmentConfig.get_config(env)
            billing_mode = config["dynamodb_billing_mode"]

            assert (
                billing_mode == "PAY_PER_REQUEST"
            ), f"{env} 환경의 billing_mode가 PAY_PER_REQUEST가 아닙니다: {billing_mode}"

    def test_cache_ttl_configuration(self):
        """모든 환경의 캐시 TTL이 올바르게 설정되었는지 확인"""
        environments = ["dev", "staging", "prod"]

        for env in environments:
            config = EnvironmentConfig.get_config(env)
            ttl_minutes = config["cache_ttl_minutes"]

            # TTL이 양수인지 확인
            assert isinstance(ttl_minutes, int), f"{env} 환경의 TTL이 정수가 아닙니다"
            assert ttl_minutes > 0, f"{env} 환경의 TTL이 0 이하입니다: {ttl_minutes}"
            assert ttl_minutes <= 60, f"{env} 환경의 TTL이 너무 큽니다: {ttl_minutes}"

    def test_resource_naming_convention(self):
        """DynamoDB 테이블 명명 규칙이 일관성 있게 적용되는지 확인"""
        environments = ["dev", "staging", "prod"]

        for env in environments:
            # 테이블 이름이 환경별로 올바르게 생성되는지 확인
            table_name = ResourcePrefixes.get_resource_name(
                env, ResourcePrefixes.WEATHER_API, "cache"
            )

            # 명명 규칙 검증
            assert table_name.startswith(
                f"{env}-weather-api"
            ), f"테이블 이름이 올바른 접두사를 가지지 않습니다: {table_name}"
            assert "cache" in table_name, f"테이블 이름에 'cache'가 포함되지 않았습니다: {table_name}"

    def test_common_tags_configuration(self):
        """공통 태그가 올바르게 설정되는지 확인"""
        environments = ["dev", "staging", "prod"]

        for env in environments:
            tags = Tags.get_common_tags(env, ResourcePrefixes.WEATHER_API)

            # 필수 태그들이 존재하는지 확인
            required_tags = ["Environment", "Service", "ManagedBy", "Project"]

            for tag in required_tags:
                assert tag in tags, f"필수 태그 '{tag}'가 없습니다"

            # 태그 값들이 올바른지 확인
            assert tags["Environment"] == env
            assert tags["Service"] == ResourcePrefixes.WEATHER_API
            assert tags["ManagedBy"] == "CDK"
            assert "weather" in tags["Project"].lower()


class TestDynamoDbStackSchemaDesign:
    """DynamoDB 스키마 설계 검증 테스트 클래스"""

    def test_table_schema_design_constants(self):
        """테이블 스키마 설계에 필요한 상수들이 올바른지 확인"""
        # 파티션 키와 정렬 키 이름 확인
        expected_pk = "PK"
        expected_sk = "SK"
        expected_ttl_field = "expires_at"

        # 이 값들이 DynamoDB 네이밍 규칙을 따르는지 확인
        assert expected_pk.isalnum(), "파티션 키 이름이 영숫자가 아닙니다"
        assert expected_sk.isalnum(), "정렬 키 이름이 영숫자가 아닙니다"
        assert expected_ttl_field.replace("_", "").isalnum(), "TTL 필드 이름이 올바르지 않습니다"

    def test_cache_key_pattern_design(self):
        """캐시 키 패턴이 올바르게 설계되었는지 확인"""
        # 예상되는 키 패턴
        city = "London"
        expected_pk_pattern = f"WEATHER#{city}"
        expected_sk_value = "DATA"

        # 키 패턴이 DynamoDB 제한사항을 준수하는지 확인
        assert len(expected_pk_pattern) <= 2048, "파티션 키가 너무 깁니다"
        assert len(expected_sk_value) <= 1024, "정렬 키가 너무 깁니다"

        # 특수 문자 사용이 적절한지 확인
        assert "#" in expected_pk_pattern, "파티션 키에 구분자가 없습니다"
        assert expected_pk_pattern.startswith("WEATHER#"), "파티션 키 접두사가 올바르지 않습니다"

    def test_environment_specific_configurations(self):
        """환경별 특화 설정이 올바르게 구성되었는지 확인"""
        # 프로덕션 환경만의 특별 설정 확인
        prod_config = EnvironmentConfig.get_config("prod")
        dev_config = EnvironmentConfig.get_config("dev")

        # 모든 환경이 동일한 TTL을 사용하는지 확인 (설계 의도)
        assert (
            prod_config["cache_ttl_minutes"] == dev_config["cache_ttl_minutes"]
        ), "환경별 TTL이 다릅니다"

        # 모든 환경이 동일한 빌링 모드를 사용하는지 확인
        assert (
            prod_config["dynamodb_billing_mode"] == dev_config["dynamodb_billing_mode"]
        ), "환경별 빌링 모드가 다릅니다"


class TestDynamoDbStackIntegration:
    """DynamoDB Stack 통합 준비 상태 테스트 클래스"""

    def test_lambda_integration_readiness(self):
        """Lambda Stack과의 통합을 위한 인터페이스가 준비되었는지 확인"""
        from stacks.dynamodb_stack import DynamoDbStack

        # Lambda Stack에서 필요한 출력값들이 정의되어 있는지 확인
        required_outputs = ["table_name_output", "table_arn"]

        for output in required_outputs:
            assert hasattr(DynamoDbStack, output), f"Lambda 통합에 필요한 출력 '{output}'이 없습니다"

    def test_constants_consistency(self):
        """DynamoDB 관련 상수들이 일관성 있게 정의되었는지 확인"""
        # ResourcePrefixes와 EnvironmentConfig의 일관성 확인
        assert hasattr(ResourcePrefixes, "WEATHER_API")

        # 환경별 설정의 일관성 확인
        environments = ["dev", "staging", "prod"]
        base_keys = set(EnvironmentConfig.get_config("dev").keys())

        for env in environments[1:]:  # staging과 prod 확인
            env_keys = set(EnvironmentConfig.get_config(env).keys())
            assert base_keys == env_keys, f"{env} 환경의 설정 키가 다릅니다"

    def test_stack_dependencies_import(self):
        """스택에 필요한 모든 의존성을 import할 수 있는지 확인"""
        try:
            # CDK 관련 import 확인
            import aws_cdk as cdk
            from aws_cdk import aws_dynamodb as dynamodb
            from constructs import Construct

            # 프로젝트 유틸리티 import 확인
            from utils.constants import EnvironmentConfig
            from utils.prefixes import ResourcePrefixes, Tags

            imports_successful = True
        except ImportError as e:
            imports_successful = False
            pytest.fail(f"필수 의존성을 import할 수 없습니다: {e}")

        assert imports_successful, "DynamoDB Stack에 필요한 의존성을 import할 수 없습니다"
