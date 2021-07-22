"""
Tests for command_context.py
"""
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException

from samcli.commands.check.lib.command_context import CheckContext


class TestCommandContext(TestCase):
    @patch("samcli.commands.check.lib.command_context.BottleNecks")
    def test_run(self, patch_bottle_neck):
        region = Mock()
        profile = Mock()
        path = Mock()
        graph_mock = Mock()
        bottle_neck_mock = Mock()
        context = CheckContext(region, profile, path)

        context.transform_template = Mock()
        context.parse_template = Mock()
        context.parse_template.return_value = graph_mock

        patch_bottle_neck.return_value = bottle_neck_mock
        bottle_neck_mock.ask_entry_point_question = Mock()

        context.run()

        context.transform_template.assert_called_once()
        context.parse_template.assert_called_once()
        patch_bottle_neck.assert_called_once_with(graph_mock)
        bottle_neck_mock.ask_entry_point_question.assert_called_once()

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
    @patch("samcli.commands.check.lib.command_context.replace_local_codeuri")
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

    @patch("samcli.commands.check.lib.command_context.GraphContext")
    @patch("samcli.commands.check.lib.command_context.LambdaFunction")
    @patch("samcli.commands.check.lib.command_context.SamLocalStackProvider")
    @patch("samcli.commands.check.lib.command_context.SamFunctionProvider")
    @patch("samcli.commands.check.lib.command_context.os")
    def test_parse_template(self, patch_os, patch_function_provider, patch_stack_provider, patch_lambda, patch_graph):
        path_mock = Mock()
        local_stacks_mock = Mock()
        stack_function_mock = Mock()

        function_provider_mock = Mock()
        function_provider_mock.get_all.return_value = [stack_function_mock]

        new_lambda_function_mock = Mock()
        patch_lambda.return_value = new_lambda_function_mock

        graph_context_mock = Mock()
        result_mock = Mock()

        graph_context_mock.generate.return_value = result_mock
        patch_graph.return_value = graph_context_mock

        all_lambda_functions = [patch_lambda.return_value]

        patch_os.path.realpath.return_value = path_mock

        patch_stack_provider.get_stacks.return_value = [local_stacks_mock]

        patch_function_provider.return_value = function_provider_mock

        context = CheckContext(Mock(), Mock(), Mock())
        result = context.parse_template()

        patch_stack_provider.get_stacks.assert_called_once_with(path_mock)
        patch_function_provider.assert_called_once_with(local_stacks_mock)
        function_provider_mock.get_all.assert_called_once()
        patch_lambda.assert_called_once_with(stack_function_mock, "AWS::Lambda::Function")
        patch_graph.assert_called_once_with(all_lambda_functions)
        graph_context_mock.generate.assert_called_once()

        self.assertEqual(result, result_mock)
