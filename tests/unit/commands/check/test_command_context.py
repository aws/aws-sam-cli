"""
Tests for command_context.py
"""
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException

from samcli.commands.check.lib.command_context import CheckContext, load_policies


class TestCommandContext(TestCase):
    def test_run(self):
        region = Mock()
        profile = Mock()
        path = Mock()
        context = CheckContext(region, profile, path)

        context.transform_template = Mock()

        context.run()

        context.transform_template.assert_called_once()

    @patch("samcli.commands.check.lib.command_context.logging")
    @patch("samcli.commands.check.lib.command_context.os.path.exists")
    def test_file_not_found(self, path_exists_patch, log_patch):
        template_path = "path_to_template"

        path_exists_patch.return_value = False

        region = Mock()
        profile = Mock()
        context = CheckContext(region, profile, template_path)

        with self.assertRaises(SamTemplateNotFoundException):
            context.read_sam_file()

    @patch("samcli.commands.check.lib.command_context.boto3")
    @patch("samcli.commands.check.lib.command_context.ManagedPolicyLoader")
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

    @patch("samcli.commands.check.lib.command_context.external_replace_local_codeuri")
    @patch("samcli.commands.check.lib.command_context.Translator")
    @patch("samcli.commands.check.lib.command_context.Session")
    @patch("samcli.commands.check.lib.command_context.parser")
    def test_transform_template(self, patched_parser, patched_session, patched_translator, patch_replace):
        self_mock = Mock()

        given_policies = Mock()
        load_policies.return_value = given_policies

        original_template = Mock()
        self_mock.read_sam_file.return_value = original_template

        updated_template = Mock()
        patch_replace.return_value = updated_template

        sam_translator = Mock()
        patched_translator.return_value = sam_translator

        converted_template = Mock()
        sam_translator.translate.return_value = converted_template

        result = CheckContext.transform_template(self_mock)

        self.assertEqual(result, converted_template)
        patch_replace.assert_called_with(original_template)
        sam_translator.translate.assert_called_with(sam_template=updated_template, parameter_values={})
