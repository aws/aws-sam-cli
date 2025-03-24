from unittest import TestCase
from unittest.mock import Mock, patch
from collections import namedtuple

from botocore.exceptions import NoCredentialsError

from samcli.commands.exceptions import UserException, LinterRuleMatchedException
from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException, InvalidSamTemplateException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.validate.validate import do_cli, _read_sam_file, _lint, SamTemplate

ctx_mock = namedtuple("ctx_mock", ["profile", "region"])
ctx_lint_mock = namedtuple("ctx_lint_mock", ["debug", "region"])


class TestValidateCli(TestCase):
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
            do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path, lint=False)

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
            do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path, lint=False)

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

        do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path, lint=False)

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

        with patch("samcli.lib.telemetry.event.EventTracker.track_event") as track_patch:
            _lint(
                ctx=ctx_lint_mock(debug=False, region="region"),
                template=template_contents,
                template_path=template_path,
                serverless_rules=True
            )
            # Check that both CFNLint and ServerlessRules events are tracked
            track_patch.assert_any_call("UsedFeature", "CFNLint")
            track_patch.assert_any_call("UsedFeature", "ServerlessRules")
            
        # Check that the lint function was called with the serverless rules
        lint_patch.assert_called_once()
        args, kwargs = lint_patch.call_args
        self.assertEqual(args[0], template_contents)
        self.assertEqual(kwargs["config"].append_rules, ["cfn_lint_serverless.rules"])
        
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
