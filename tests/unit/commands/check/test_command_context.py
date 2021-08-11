"""
Tests for command_context.py
"""
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


from samcli.commands.check.lib.command_context import CheckContext, _parse_template


class TestCommandContext(TestCase):
    @patch("samcli.commands.check.lib.command_context.CheckResults")
    @patch("samcli.commands.check.lib.command_context.LambdaFunctionPricingCalculations")
    @patch("samcli.commands.check.lib.command_context.BottleNeckCalculations")
    @patch("samcli.commands.check.lib.command_context._parse_template")
    @patch("samcli.commands.check.lib.command_context.BottleNecks")
    def test_run(
        self,
        patch_bottle_neck,
        patch_parse_template,
        patch_bottle_neck_calculations,
        patch_lambda_pricing_calculations,
        patch_print,
    ):
        region = Mock()
        profile = Mock()
        path = Mock()
        graph_mock = Mock()
        bottle_neck_mock = Mock()
        context = CheckContext(region, profile, path)

        context._transform_template = Mock()

        patch_parse_template.return_value = graph_mock

        patch_bottle_neck.return_value = bottle_neck_mock
        bottle_neck_mock.ask_entry_point_question = Mock()

        patch_bottle_neck_calculations.run_bottle_neck_calculations = Mock()
        patch_print.print_bottle_neck_results = Mock()

        patch_lambda_pricing_calculations.run_calculations = Mock()
        patch_lambda_pricing_calculations.lambda_pricing_results = Mock()

        patch_parse_template.return_value = graph_mock

        patch_bottle_neck.return_value = bottle_neck_mock
        bottle_neck_mock.ask_entry_point_question = Mock()

        context.run()

        context._transform_template.assert_called_once()
        patch_parse_template.assert_called_once()
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
            context._read_sam_file()

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
        context._read_sam_file = Mock()
        context._read_sam_file.return_value = original_template

        updated_template = Mock()
        patch_replace.return_value = updated_template

        sam_translator = Mock()
        patched_translator.return_value = sam_translator

        converted_template = Mock()
        sam_translator.translate.return_value = converted_template

        result = context._transform_template()

        self.assertEqual(result, converted_template)
        patch_replace.assert_called_with(original_template)
        sam_translator.translate.assert_called_with(sam_template=updated_template, parameter_values={})

    @patch("samcli.commands.check.lib.command_context.CheckGraph")
    @patch("samcli.commands.check.lib.command_context.LambdaFunction")
    @patch("samcli.commands.check.lib.command_context.SamLocalStackProvider")
    @patch("samcli.commands.check.lib.command_context.SamFunctionProvider")
    @patch("samcli.commands.check.lib.command_context.os")
    def test_parse_template(self, patch_os, patch_function_provider, patch_stack_provider, patch_lambda, patch_graph):
        path_mock = Mock()
        local_stacks_mock = Mock()
        stack_function_mock = Mock()
        stack_function_mock.name = Mock()

        function_provider_mock = Mock()
        function_provider_mock.get_all.return_value = [stack_function_mock]

        new_lambda_function_mock = Mock()
        patch_lambda.return_value = new_lambda_function_mock

        graph_mock = Mock()

        patch_graph.return_value = graph_mock

        all_lambda_functions = [patch_lambda.return_value]

        patch_os.path.realpath.return_value = path_mock

        patch_stack_provider.get_stacks.return_value = [local_stacks_mock]

        patch_function_provider.return_value = function_provider_mock

        result = _parse_template()

        patch_stack_provider.get_stacks.assert_called_once_with(path_mock)
        patch_function_provider.assert_called_once_with(local_stacks_mock)
        function_provider_mock.get_all.assert_called_once()
        patch_lambda.assert_called_once_with(stack_function_mock, AWS_LAMBDA_FUNCTION, stack_function_mock.name)
        patch_graph.assert_called_once_with(all_lambda_functions)

        self.assertEqual(result, graph_mock)
