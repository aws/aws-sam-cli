from unittest import TestCase
from unittest.mock import Mock, patch
from collections import namedtuple

from botocore.exceptions import NoCredentialsError

from cfnlint.core import CfnLintExitException, InvalidRegionException  # type: ignore

from samcli.commands.exceptions import UserException, LinterRuleMatchedException
from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException, InvalidSamTemplateException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.validate.validate import do_cli, _read_sam_file, _lint

ctx_mock = namedtuple("ctx", ["profile", "region"])
ctx_lint_mock = namedtuple("ctx", ["debug", "region"])


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

        self.assertEqual(actual_template, {"a": "b"})

    @patch("samcli.lib.translate.sam_template_validator.SamTemplateValidator")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate._read_sam_file")
    @patch("boto3.client")
    def test_template_fails_validation(self, patched_boto, read_sam_file_patch, click_patch, template_valiadator):
        template_path = "path_to_template"
        read_sam_file_patch.return_value = {"a": "b"}

        get_translated_template_if_valid_mock = Mock()
        get_translated_template_if_valid_mock.get_translated_template_if_valid.side_effect = InvalidSamDocumentException
        template_valiadator.return_value = get_translated_template_if_valid_mock

        with self.assertRaises(InvalidSamTemplateException):
            do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path, lint=False)

    @patch("samcli.lib.translate.sam_template_validator.SamTemplateValidator")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate._read_sam_file")
    @patch("boto3.client")
    def test_no_credentials_provided(self, patched_boto, read_sam_file_patch, click_patch, template_valiadator):
        template_path = "path_to_template"
        read_sam_file_patch.return_value = {"a": "b"}

        get_translated_template_if_valid_mock = Mock()
        get_translated_template_if_valid_mock.get_translated_template_if_valid.side_effect = NoCredentialsError
        template_valiadator.return_value = get_translated_template_if_valid_mock

        with self.assertRaises(UserException):
            do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path, lint=False)

    @patch("samcli.lib.translate.sam_template_validator.SamTemplateValidator")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate._read_sam_file")
    @patch("boto3.client")
    def test_template_passes_validation(self, patched_boto, read_sam_file_patch, click_patch, template_valiadator):
        template_path = "path_to_template"
        read_sam_file_patch.return_value = {"a": "b"}

        get_translated_template_if_valid_mock = Mock()
        get_translated_template_if_valid_mock.get_translated_template_if_valid.return_value = True
        template_valiadator.return_value = get_translated_template_if_valid_mock

        do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path, lint=False)

    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate._lint")
    def test_lint_template_passes(self, click_patch, lint_patch):
        template_path = "path_to_template"

        lint_patch.return_value = True

        do_cli(ctx=ctx_lint_mock(debug=False, region="region"), template=template_path, lint=True)

    @patch("cfnlint.core.get_args_filenames")
    @patch("cfnlint.core.get_matches")
    @patch("samcli.commands.validate.validate.click")
    def test_lint_invalid_region_argument_fails(self, click_patch, matches_patch, args_patch):
        template_path = "path_to_template"

        args_patch.return_value = ("A", "B", "C")

        matches_patch.side_effect = InvalidRegionException

        with self.assertRaises(UserException):
            _lint(ctx=ctx_lint_mock(debug=False, region="region"), template=template_path)

    @patch("cfnlint.core.get_args_filenames")
    @patch("cfnlint.core.get_matches")
    @patch("samcli.commands.validate.validate.click")
    def test_lint_exception_fails(self, click_patch, matches_patch, args_patch):
        template_path = "path_to_template"

        args_patch.return_value = ("A", "B", "C")

        matches_patch.side_effect = CfnLintExitException

        with self.assertRaises(UserException):
            _lint(ctx=ctx_lint_mock(debug=False, region="region"), template=template_path)

    @patch("samcli.commands.validate.validate.click")
    def test_lint_event_recorded(self, click_patch):
        template_path = "path_to_template"

        with patch("samcli.lib.telemetry.event.EventTracker.track_event") as track_patch:
            with self.assertRaises(LinterRuleMatchedException):
                _lint(ctx=ctx_lint_mock(debug=False, region="region"), template=template_path)
            track_patch.assert_called_with("UsedFeature", "CFNLint")

    @patch("cfnlint.core.get_args_filenames")
    @patch("cfnlint.core.get_matches")
    @patch("samcli.commands.validate.validate.click")
    def test_linter_raises_exception_if_matches_found(self, click_patch, matches_patch, args_patch):
        template_path = "path_to_template"
        args_patch.return_value = ("A", "B", Mock())
        matches_patch.return_value = ["Failed rule A", "Failed rule B"]
        with self.assertRaises(LinterRuleMatchedException) as ex:
            _lint(ctx=ctx_lint_mock(debug=False, region="region"), template=template_path)
        self.assertEqual(
            ex.exception.message, "Linting failed. At least one linting rule was matched to the provided template."
        )
