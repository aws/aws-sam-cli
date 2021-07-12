from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.command import _read_sam_file, load_policies, replace_code_uri, transform_template
from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException, InvalidSamTemplateException


class TestCheckCli(TestCase):
    @patch("samcli.commands.check.command.click")
    @patch("samcli.commands.check.command.os.path.exists")
    def test_file_not_found(self, path_exists_patch, click_patch):
        template_path = "path_to_template"

        path_exists_patch.return_value = False

        with self.assertRaises(SamTemplateNotFoundException):
            _read_sam_file(template_path)

    @patch("samcli.commands.check.command.boto3")
    @patch("samcli.commands.check.command.ManagedPolicyLoader")
    def test_load_policies(self, policy_loader_mock, boto3_mock):
        mock_iam_client = Mock()
        boto3_mock.client.return_value = mock_iam_client

        expected_policies = Mock()

        mock_loader = Mock()
        policy_loader_mock.return_value = mock_loader

        mock_loader.load.return_value = expected_policies

        result = load_policies()

        boto3_mock.client.assert_called_with("iam")
        policy_loader_mock.assert_called_with(mock_iam_client)

        mock_loader.load.assert_called_once()
        self.assertEqual(result, expected_policies)

    @patch("samcli.commands.check.command.ReplaceLocalCodeUri")
    def test_replace_code_uri(self, patched_replace):
        uri_replace = Mock()
        patched_replace.return_value = uri_replace

        expected_value = Mock()
        uri_replace._replace_local_codeuri.return_value = expected_value

        template = Mock()
        result = replace_code_uri(template)

        self.assertEqual(expected_value, result)
        uri_replace._replace_local_codeuri.assert_called_once()
        patched_replace.assert_called_with(template)

    @patch("samcli.commands.check.command.load_policies")
    @patch("samcli.commands.check.command._read_sam_file")
    @patch("samcli.commands.check.command.replace_code_uri")
    @patch("samcli.commands.check.command.Translator")
    @patch("samcli.commands.check.command.Session")
    @patch("samcli.commands.check.command.parser")
    def test_transform_template(
        self, patched_parser, patched_session, patched_translator, patched_replace, patched_read, patched_load
    ):
        given_policies = Mock()
        patched_load.return_value = given_policies

        original_template = Mock()
        patched_read.return_value = original_template

        updated_template = Mock()
        patched_replace.return_value = updated_template

        sam_translator = Mock()
        patched_translator.return_value = sam_translator

        converted_template = Mock()
        sam_translator.translate.return_value = converted_template

        template_path = Mock()
        result = transform_template(Mock(), template_path)

        self.assertEqual(result, converted_template)
        patched_read.assert_called_with(template_path)
        patched_replace.assert_called_with(original_template)
        sam_translator.translate.assert_called_with(sam_template=updated_template, parameter_values={})
