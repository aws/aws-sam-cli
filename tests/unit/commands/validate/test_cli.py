from unittest import TestCase
from unittest.mock import Mock, patch
from collections import namedtuple

from botocore.exceptions import NoCredentialsError

from samcli.commands.exceptions import UserException
from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException, InvalidSamTemplateException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.validate.validate import do_cli, _read_sam_file

ctx_mock = namedtuple("ctx", ["profile", "region"])


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

    @patch("samcli.commands.validate.lib.sam_template_validator.SamTemplateValidator")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate._read_sam_file")
    def test_template_fails_validation(self, read_sam_file_patch, click_patch, template_valiadator):
        template_path = "path_to_template"
        read_sam_file_patch.return_value = {"a": "b"}

        is_valid_mock = Mock()
        is_valid_mock.is_valid.side_effect = InvalidSamDocumentException
        template_valiadator.return_value = is_valid_mock

        with self.assertRaises(InvalidSamTemplateException):
            do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path)

    @patch("samcli.commands.validate.lib.sam_template_validator.SamTemplateValidator")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate._read_sam_file")
    def test_no_credentials_provided(self, read_sam_file_patch, click_patch, template_valiadator):
        template_path = "path_to_template"
        read_sam_file_patch.return_value = {"a": "b"}

        is_valid_mock = Mock()
        is_valid_mock.is_valid.side_effect = NoCredentialsError
        template_valiadator.return_value = is_valid_mock

        with self.assertRaises(UserException):
            do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path)

    @patch("samcli.commands.validate.lib.sam_template_validator.SamTemplateValidator")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate._read_sam_file")
    def test_template_passes_validation(self, read_sam_file_patch, click_patch, template_valiadator):
        template_path = "path_to_template"
        read_sam_file_patch.return_value = {"a": "b"}

        is_valid_mock = Mock()
        is_valid_mock.is_valid.return_value = True
        template_valiadator.return_value = is_valid_mock

        do_cli(ctx=ctx_mock(profile="profile", region="region"), template=template_path)
