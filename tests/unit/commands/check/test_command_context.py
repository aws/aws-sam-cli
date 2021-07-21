"""
Tests for command_context.py
"""
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException

from samcli.commands.check.lib.command_context import CheckContext


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

    @patch("samcli.commands.check.lib.command_context.SamTranslatorWrapper")
    @patch("samcli.commands.check.lib.command_context.external_replace_local_codeuri")
    @patch("samcli.commands.check.lib.command_context.Translator")
    @patch("samcli.commands.check.lib.command_context.Session")
    @patch("samcli.commands.check.lib.command_context.parser")
    def test_transform_template(
        self, patched_parser, patched_session, patched_translator, patch_replace, patch_wrapper
    ):
        """
        read_sam_file needs to be cast as a mock through context
        load_policies needs to be mocked through @patch
        """
        region = Mock()
        profile = Mock()
        template_path = Mock()

        context = CheckContext(region, profile, template_path)

        given_policies = Mock()
        patch_wrapper.managed_policy_map.return_value = given_policies

        original_template = Mock()
        context.read_sam_file = Mock()
        context.read_sam_file.return_value = original_template

        updated_template = Mock()
        patch_replace.return_value = updated_template

        sam_translator = Mock()
        patched_translator.return_value = sam_translator

        converted_template = Mock()
        sam_translator.translate.return_value = converted_template

        result = context.transform_template()

        self.assertEqual(result, converted_template)
        patch_replace.assert_called_with(original_template)
        sam_translator.translate.assert_called_with(sam_template=updated_template, parameter_values={})
