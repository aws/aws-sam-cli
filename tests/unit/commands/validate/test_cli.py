from unittest import TestCase
from unittest.mock import Mock, patch
from collections import namedtuple
import warnings

from botocore.exceptions import NoCredentialsError

from samcli.commands.exceptions import UserException, LinterRuleMatchedException
from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException, InvalidSamTemplateException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.validate.validate import do_cli, _read_sam_file, _lint, SamTemplate, cli

ctx_mock = namedtuple("ctx_mock", ["profile", "region"])
ctx_lint_mock = namedtuple("ctx_lint_mock", ["debug", "region"])


class TestValidateCli(TestCase):
    def setUp(self):
        # datetime.utcnow() 사용에 대한 경고 무시
        warnings.filterwarnings("ignore", category=DeprecationWarning, message="datetime.datetime.utcnow()")

    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate.os.path.exists")
    def test_file_not_found(self, path_exists_patch, click_patch):
        template_path = "path_to_template"

        path_exists_patch.return_value = False

        with self.assertRaises(SamTemplateNotFoundException):
            _read_sam_file(template_path)

    @patch("samcli.yamlhelper.yaml_parse")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate.os.path.exists")
    def test_file_parsed(self, path_exists_patch, click_patch, yaml_parse_patch):
        template_path = "path_to_template"

        path_exists_patch.return_value = True

        yaml_parse_patch.return_value = {"a": "b"}

        actual_template = _read_sam_file(template_path)

        self.assertEqual(actual_template.deserialized, {"a": "b"})

    @patch("samcli.lib.translate.sam_template_validator.SamTemplateValidator")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate._read_sam_file")
    @patch("boto3.client")
    def test_template_fails_validation(self, patched_boto, read_sam_file_patch, click_patch, template_validator):
        template_path = "path_to_template"
        read_sam_file_patch.return_value = SamTemplate(deserialized={"a": "b"}, serialized="")

        get_translated_template_if_valid_mock = Mock()
        get_translated_template_if_valid_mock.get_translated_template_if_valid.side_effect = InvalidSamDocumentException
        template_validator.return_value = get_translated_template_if_valid_mock

        with self.assertRaises(InvalidSamTemplateException):
            do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path, lint=False, serverless_rules=False)

    @patch("samcli.lib.translate.sam_template_validator.SamTemplateValidator")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate._read_sam_file")
    @patch("boto3.client")
    def test_no_credentials_provided(self, patched_boto, read_sam_file_patch, click_patch, template_validator):
        template_path = "path_to_template"
        read_sam_file_patch.return_value = SamTemplate(deserialized={"a": "b"}, serialized="")

        get_translated_template_if_valid_mock = Mock()
        get_translated_template_if_valid_mock.get_translated_template_if_valid.side_effect = NoCredentialsError
        template_validator.return_value = get_translated_template_if_valid_mock

        with self.assertRaises(UserException):
            do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path, lint=False, serverless_rules=False)

    @patch("samcli.lib.translate.sam_template_validator.SamTemplateValidator")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate._read_sam_file")
    @patch("boto3.client")
    def test_template_passes_validation(self, patched_boto, read_sam_file_patch, click_patch, template_validator):
        template_path = "path_to_template"
        read_sam_file_patch.return_value = SamTemplate(deserialized={"a": "b"}, serialized="")

        get_translated_template_if_valid_mock = Mock()
        get_translated_template_if_valid_mock.get_translated_template_if_valid.return_value = True
        template_validator.return_value = get_translated_template_if_valid_mock

        do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path, lint=False, serverless_rules=False)

    @patch("samcli.commands.validate.validate._read_sam_file")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate._lint")
    def test_lint_template_passes(self, lint_patch, click_patch, read_sam_file_patch):
        template_path = "path_to_template"

        read_sam_file_patch.return_value = SamTemplate(serialized="{}", deserialized={})
        lint_patch.return_value = True

        do_cli(ctx=ctx_lint_mock(debug=False, region="region"), template=template_path, lint=True, serverless_rules=False)

    @patch("cfnlint.api.lint")
    @patch("samcli.commands.validate.validate.click")
    def test_lint_event_recorded(self, click_patch, lint_patch):
        template_path = "path_to_template"
        template_contents = "{}"

        with patch("samcli.lib.telemetry.event.EventTracker.track_event") as track_patch:
            with self.assertRaises(LinterRuleMatchedException):
                _lint(
                    ctx=ctx_lint_mock(debug=False, region="region"),
                    template=template_contents,
                    template_path=template_path,
                    serverless_rules=False
                )
            track_patch.assert_called_with("UsedFeature", "CFNLint")

    @patch("cfnlint.api.lint")
    @patch("samcli.commands.validate.validate.click")
    def test_linter_raises_exception_if_matches_found(self, click_patch, lint_patch):
        template_path = "path_to_template"
        template_contents = "{}"

        lint_patch.return_value = ["Failed rule A", "Failed rule B"]

        with self.assertRaises(LinterRuleMatchedException) as ex:
            _lint(
                ctx=ctx_lint_mock(debug=False, region="region"), 
                template=template_contents, 
                template_path=template_path,
                serverless_rules=False
            )

        self.assertEqual(
            ex.exception.message, "Linting failed. At least one linting rule was matched to the provided template."
        )
        
    @patch("cfnlint.api.lint")
    @patch("samcli.commands.validate.validate.click")
    @patch("importlib.util.find_spec")
    def test_serverless_rules_enabled(self, find_spec_mock, click_patch, lint_patch):
        template_path = "path_to_template"
        template_contents = "{}"
        find_spec_mock.return_value = True
        lint_patch.return_value = []

        # ManualArgs 클래스를 모킹하여 append_rules 속성이 올바르게 설정되도록 함
        with patch("samcli.lib.telemetry.event.EventTracker.track_event") as track_patch:
            with patch("cfnlint.api.ManualArgs") as manual_args_mock:
                # ManualArgs 객체가 append_rules 속성을 가지도록 설정
                manual_args_instance = Mock()
                manual_args_mock.return_value = manual_args_instance
                
                _lint(
                    ctx=ctx_lint_mock(debug=False, region="region"),
                    template=template_contents,
                    template_path=template_path,
                    serverless_rules=True
                )
                
                # Check that both CFNLint and ServerlessRules events are tracked
                track_patch.assert_any_call("UsedFeature", "CFNLint")
                track_patch.assert_any_call("UsedFeature", "ServerlessRules")
                
                # Check that the ManualArgs was called with the serverless rules
                manual_args_mock.assert_called_once()
                args, kwargs = manual_args_mock.call_args
                self.assertIn("append_rules", kwargs)
                self.assertEqual(kwargs["append_rules"], ["cfn_lint_serverless.rules"])
                
    @patch("cfnlint.api.lint")
    @patch("samcli.commands.validate.validate.click")
    @patch("importlib.util.find_spec")
    def test_serverless_rules_package_not_installed(self, find_spec_mock, click_patch, lint_patch):
        template_path = "path_to_template"
        template_contents = "{}"
        find_spec_mock.return_value = None

        with self.assertRaises(UserException) as ex:
            _lint(
                ctx=ctx_lint_mock(debug=False, region="region"),
                template=template_contents,
                template_path=template_path,
                serverless_rules=True
            )
            
        self.assertIn("Serverless Rules package (cfn-lint-serverless) is not installed", ex.exception.message)
        
    @patch("samcli.commands.validate.validate._read_sam_file")
    def test_cli_with_extra_lint_rules(self, mock_read_sam_file):
        # 테스트 준비
        template = "template"
        extra_lint_rules = "cfn_lint_serverless.rules"
        mock_read_sam_file.return_value = SamTemplate(serialized="", deserialized={})
        
        # do_cli 함수를 직접 테스트
        with patch("samcli.commands.validate.validate._lint") as mock_lint:
            # do_cli 호출
            do_cli(
                ctx=ctx_mock(profile="profile", region="region"), 
                template=template, 
                lint=True, 
                serverless_rules=False,
                extra_lint_rules=extra_lint_rules
            )
            
            # _lint이 올바른 파라미터로 호출되는지 확인
            mock_lint.assert_called_once()
            args, kwargs = mock_lint.call_args
            self.assertEqual(args[2], template)  # template_path 파라미터
            self.assertEqual(args[3], False)     # serverless_rules 파라미터
            self.assertEqual(args[4], extra_lint_rules)  # extra_lint_rules 파라미터
        
    @patch("cfnlint.api.lint")
    @patch("samcli.commands.validate.validate.click")
    def test_lint_with_extra_lint_rules(self, click_patch, lint_patch):
        # 테스트 준비
        template_path = "path_to_template"
        template_contents = "{}"
        extra_lint_rules = "custom.rules.module"
        lint_patch.return_value = []
        
        # ManualArgs 클래스를 모킹하여 append_rules 속성이 올바르게 설정되는지 확인
        with patch("samcli.lib.telemetry.event.EventTracker.track_event") as track_patch:
            with patch("cfnlint.api.ManualArgs") as manual_args_mock:
                # ManualArgs 객체가 append_rules 속성을 가지도록 설정
                manual_args_instance = Mock()
                manual_args_mock.return_value = manual_args_instance
                
                # 테스트 실행
                _lint(
                    ctx=ctx_lint_mock(debug=False, region="region"),
                    template=template_contents,
                    template_path=template_path,
                    serverless_rules=False,
                    extra_lint_rules=extra_lint_rules
                )
                
                # 이벤트 추적 확인 - ExtraLintRules 이벤트가 추적되는지 확인
                track_patch.assert_any_call("UsedFeature", "CFNLint")
                track_patch.assert_any_call("UsedFeature", "ExtraLintRules")
                
                # ManualArgs가 올바른 인자와 함께 호출되는지 확인
                manual_args_mock.assert_called_once()
                args, kwargs = manual_args_mock.call_args
                self.assertIn("append_rules", kwargs)
                self.assertEqual(kwargs["append_rules"], [extra_lint_rules])
                
    @patch("cfnlint.api.lint")
    @patch("samcli.commands.validate.validate.click")
    def test_lint_with_multiple_comma_separated_extra_lint_rules(self, click_patch, lint_patch):
        # 테스트 준비
        template_path = "path_to_template"
        template_contents = "{}"
        # 콤마로 구분된 여러 규칙 모듈 지정
        extra_lint_rules = "module1.rules,module2.rules,module3.rules"
        lint_patch.return_value = []
        
        # ManualArgs 클래스를 모킹하여 append_rules 속성이 올바르게 설정되는지 확인
        with patch("samcli.lib.telemetry.event.EventTracker.track_event"):
            with patch("cfnlint.api.ManualArgs") as manual_args_mock:
                manual_args_instance = Mock()
                manual_args_mock.return_value = manual_args_instance
                
                # 테스트 실행
                _lint(
                    ctx=ctx_lint_mock(debug=False, region="region"),
                    template=template_contents,
                    template_path=template_path,
                    serverless_rules=False,
                    extra_lint_rules=extra_lint_rules
                )
                
                # ManualArgs가 올바른 인자와 함께 호출되는지 확인
                manual_args_mock.assert_called_once()
                args, kwargs = manual_args_mock.call_args
                self.assertIn("append_rules", kwargs)
                # 콤마로 구분된 각 모듈이 분리되어 리스트에 추가되는지 확인
                expected_rules = ["module1.rules", "module2.rules", "module3.rules"]
                self.assertEqual(set(kwargs["append_rules"]), set(expected_rules))
                
    @patch("cfnlint.api.lint")
    @patch("samcli.commands.validate.validate.click")
    @patch("importlib.util.find_spec")
    def test_serverless_rules_deprecated_with_extra_lint_rules(self, find_spec_mock, click_patch, lint_patch):
        # 테스트 준비
        template_path = "path_to_template"
        template_contents = "{}"
        find_spec_mock.return_value = True
        lint_patch.return_value = []
        
        # 두 옵션이 모두 제공되었을 때 extra_lint_rules가 우선되는지 확인
        with patch("samcli.lib.telemetry.event.EventTracker.track_event"):
            with patch("cfnlint.api.ManualArgs") as manual_args_mock:
                manual_args_instance = Mock()
                manual_args_mock.return_value = manual_args_instance
                
                # 테스트 실행 - 두 옵션 모두 사용
                _lint(
                    ctx=ctx_lint_mock(debug=False, region="region"),
                    template=template_contents,
                    template_path=template_path,
                    serverless_rules=True,
                    extra_lint_rules="custom.rules.module"
                )
                
                # 검증 - 두 규칙이 모두 추가되는지 확인
                manual_args_mock.assert_called_once()
                args, kwargs = manual_args_mock.call_args
                self.assertIn("append_rules", kwargs)
                self.assertEqual(len(kwargs["append_rules"]), 2)
                self.assertIn("cfn_lint_serverless.rules", kwargs["append_rules"])
                self.assertIn("custom.rules.module", kwargs["append_rules"])
