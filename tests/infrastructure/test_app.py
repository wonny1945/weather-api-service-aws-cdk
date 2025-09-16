"""
Infrastructure app.py 테스트 모듈
app.py의 주요 함수들에 대한 단위 테스트:
- get_aws_account_and_region(): AWS 계정/리전 정보 가져오기
- parse_arguments(): 명령어 인자 파싱
- main(): 메인 함수 통합 테스트
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from argparse import Namespace

# infrastructure 모듈을 import할 수 있도록 path 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../infrastructure"))

from app import get_aws_account_and_region, parse_arguments, main


class TestGetAwsAccountAndRegion:
    """AWS 계정 및 리전 정보 가져오기 함수 테스트"""

    @patch("app.boto3.Session")
    def test_success_case(self, mock_session):
        """정상적으로 AWS 정보를 가져오는 경우"""
        # Mock 설정
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}

        mock_session_instance = Mock()
        mock_session_instance.client.return_value = mock_sts_client
        mock_session_instance.region_name = "us-east-1"
        mock_session.return_value = mock_session_instance

        # 함수 실행
        account, region = get_aws_account_and_region()

        # 검증
        assert account == "123456789012"
        assert region == "us-east-1"
        mock_session.assert_called_once()
        mock_session_instance.client.assert_called_once_with("sts")
        mock_sts_client.get_caller_identity.assert_called_once()

    @patch("app.boto3.Session")
    def test_no_credentials_error(self, mock_session):
        """AWS 인증 정보가 없는 경우"""
        from botocore.exceptions import NoCredentialsError

        mock_session.side_effect = NoCredentialsError()

        # 함수 실행
        account, region = get_aws_account_and_region()

        # 검증
        assert account is None
        assert region is None

    @patch("app.boto3.Session")
    def test_profile_not_found_error(self, mock_session):
        """AWS 프로필을 찾을 수 없는 경우"""
        from botocore.exceptions import ProfileNotFound

        mock_session.side_effect = ProfileNotFound(profile="default")

        # 함수 실행
        account, region = get_aws_account_and_region()

        # 검증
        assert account is None
        assert region is None

    @patch("app.boto3.Session")
    def test_general_exception(self, mock_session):
        """기타 예외 발생 경우"""
        mock_session.side_effect = Exception("General AWS error")

        # 함수 실행
        account, region = get_aws_account_and_region()

        # 검증
        assert account is None
        assert region is None


class TestParseArguments:
    """명령어 인자 파싱 함수 테스트"""

    @patch("sys.argv", ["app.py", "--env", "dev"])
    def test_env_argument(self):
        """--env 인자 파싱 테스트"""
        args = parse_arguments()
        assert args.env == "dev"
        assert args.account is None
        assert args.region is None

    @patch(
        "sys.argv",
        [
            "app.py",
            "--env",
            "staging",
            "--account",
            "123456789",
            "--region",
            "us-west-2",
        ],
    )
    def test_all_arguments(self):
        """모든 인자 파싱 테스트"""
        args = parse_arguments()
        assert args.env == "staging"
        assert args.account == "123456789"
        assert args.region == "us-west-2"

    @patch("sys.argv", ["app.py"])
    def test_no_arguments(self):
        """인자 없이 실행하는 경우"""
        args = parse_arguments()
        assert args.env is None
        assert args.account is None
        assert args.region is None

    @patch("sys.argv", ["app.py", "--env", "invalid"])
    def test_invalid_env_argument(self):
        """잘못된 환경 값 입력 시 오류 발생"""
        with pytest.raises(SystemExit):
            parse_arguments()


class TestMainFunction:
    """메인 함수 통합 테스트"""

    @patch("app.parse_arguments")
    @patch("app.get_aws_account_and_region")
    @patch("app.cdk.App")
    @patch("builtins.print")
    @patch("os.getenv")
    def test_main_with_command_line_args(
        self, mock_getenv, mock_print, mock_app, mock_get_aws, mock_parse_args
    ):
        """명령어 인자가 있는 경우 메인 함수 테스트"""
        # Mock 설정
        mock_parse_args.return_value = Namespace(
            env="prod", account="987654321", region="ap-northeast-2"
        )
        mock_get_aws.return_value = ("123456789", "us-east-1")

        mock_app_instance = Mock()
        mock_app_instance.node.try_get_context.return_value = None
        mock_app_instance.synth = Mock()
        mock_app.return_value = mock_app_instance

        # 함수 실행
        main()

        # 검증
        mock_parse_args.assert_called_once()
        mock_get_aws.assert_called_once()
        mock_app.assert_called_once()
        mock_app_instance.synth.assert_called_once()

        # print 호출 확인 (명령어 인자 값들이 사용되는지)
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("prod" in call for call in print_calls)
        assert any("987654321" in call for call in print_calls)
        assert any("ap-northeast-2" in call for call in print_calls)

    @patch("app.parse_arguments")
    @patch("app.get_aws_account_and_region")
    @patch("app.cdk.App")
    @patch("builtins.print")
    @patch("os.getenv")
    def test_main_with_context_fallback(
        self, mock_getenv, mock_print, mock_app, mock_get_aws, mock_parse_args
    ):
        """CDK context로 fallback하는 경우 테스트"""
        # Mock 설정
        mock_parse_args.return_value = Namespace(env=None, account=None, region=None)
        mock_get_aws.return_value = ("123456789", "us-east-1")

        mock_app_instance = Mock()
        mock_app_instance.node.try_get_context.return_value = "staging"
        mock_app_instance.synth = Mock()
        mock_app.return_value = mock_app_instance

        mock_getenv.return_value = None

        # 함수 실행
        main()

        # 검증
        mock_app_instance.node.try_get_context.assert_called_once_with("env")
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("staging" in call for call in print_calls)

    @patch("app.parse_arguments")
    @patch("app.get_aws_account_and_region")
    @patch("app.cdk.App")
    @patch("builtins.print")
    @patch("os.getenv")
    def test_main_with_env_var_fallback(
        self, mock_getenv, mock_print, mock_app, mock_get_aws, mock_parse_args
    ):
        """환경변수로 fallback하는 경우 테스트"""
        # Mock 설정
        mock_parse_args.return_value = Namespace(env="dev", account=None, region=None)
        mock_get_aws.return_value = (None, None)  # AWS config에서 못 가져온 경우

        mock_app_instance = Mock()
        mock_app_instance.node.try_get_context.return_value = None
        mock_app_instance.synth = Mock()
        mock_app.return_value = mock_app_instance

        # 환경변수 mock
        def getenv_side_effect(key):
            if key == "CDK_DEFAULT_ACCOUNT":
                return "999888777"
            elif key == "CDK_DEFAULT_REGION":
                return "eu-west-1"
            return None

        mock_getenv.side_effect = getenv_side_effect

        # 함수 실행
        main()

        # 검증
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("999888777" in call for call in print_calls)
        assert any("eu-west-1" in call for call in print_calls)

    @patch("app.parse_arguments")
    @patch("app.get_aws_account_and_region")
    @patch("app.cdk.App")
    @patch("builtins.print")
    @patch("os.getenv")
    def test_main_default_values(
        self, mock_getenv, mock_print, mock_app, mock_get_aws, mock_parse_args
    ):
        """기본값으로 fallback하는 경우 테스트"""
        # Mock 설정 - 모든 소스에서 값을 못 가져온 경우
        mock_parse_args.return_value = Namespace(env=None, account=None, region=None)
        mock_get_aws.return_value = (None, None)

        mock_app_instance = Mock()
        mock_app_instance.node.try_get_context.return_value = None
        mock_app_instance.synth = Mock()
        mock_app.return_value = mock_app_instance

        mock_getenv.return_value = None

        # 함수 실행
        main()

        # 검증 - dev가 기본값으로 사용되는지 확인
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("dev" in call for call in print_calls)
