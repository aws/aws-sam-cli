from unittest import TestCase
from unittest.mock import patch, MagicMock, Mock

import click

from samcli.commands._utils.iac_validations import iac_options_validation


def _make_ctx_params_side_effect_func(params):
    def side_effect(key, default=None):
        return params.get(key, default)

    return side_effect


class TestIacValidations(TestCase):
    def setUp(self):
        @iac_options_validation(require_stack=False)
        def func_not_require_stack(*args, **kwargs):
            pass

        @iac_options_validation(require_stack=True)
        def func_require_stack(*args, **kwargs):
            pass

        self.func_require_stack = func_require_stack
        self.func_not_require_stack = func_not_require_stack

    @patch("samcli.commands._utils.iac_validations.click")
    def test_validation_success_cfn_not_require_stack(self, click_mock):
        params = {"project_type": "CFN"}
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        click_mock.get_current_context.return_value = context_mock

        project_mock = Mock()
        self.func_not_require_stack(project=project_mock)

    @patch("samcli.commands._utils.iac_validations.click")
    def test_validation_success_cfn_require_stack(self, click_mock):
        params = {"project_type": "CFN"}
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        click_mock.get_current_context.return_value = context_mock

        project_mock = Mock()
        self.func_require_stack(project=project_mock)

    @patch("samcli.commands._utils.iac_validations.click")
    def test_validation_fail_cfn_missing_stack_name_when_deploy(self, click_mock):
        params = {"project_type": "CFN"}
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        context_mock.command.name = "deploy"
        click_mock.get_current_context.return_value = context_mock
        click_mock.BadOptionUsage = click.BadOptionUsage

        project_mock = Mock()
        with self.assertRaises(click_mock.BadOptionUsage) as ex:
            self.func_require_stack(project=project_mock)
        self.assertEqual(ex.exception.option_name, "--stack-name")
        self.assertEqual(
            ex.exception.message,
            "Missing option '--stack-name', 'sam deploy --guided' can "
            "be used to provide and save needed parameters for future deploys.",
        )

    @patch("samcli.commands._utils.iac_validations.click")
    def test_validation_fail_cfn_invalid_options(self, click_mock):
        params = {
            "project_type": "CFN",
            "cdk_app": "foo",
        }
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        click_mock.get_current_context.return_value = context_mock
        click_mock.BadOptionUsage = click.BadOptionUsage

        project_mock = Mock()
        with self.assertRaises(click_mock.BadOptionUsage) as ex:
            self.func_require_stack(project=project_mock)
        self.assertEqual(ex.exception.option_name, "--cdk-app")
        self.assertEqual(ex.exception.message, "Option '--cdk-app' cannot be used for Project Type 'CFN'")

    @patch("samcli.commands._utils.iac_validations.click")
    def test_validation_success_cdk_not_require_stack(self, click_mock):
        params = {
            "project_type": "CDK",
            "cdk_app": "foo",
        }
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        click_mock.get_current_context.return_value = context_mock
        click_mock.BadOptionUsage = click.BadOptionUsage

        project_mock = Mock()
        stack_mock = Mock()
        stack_mock.name = "stack"
        project_mock.stacks = [stack_mock]

        self.func_not_require_stack(project=project_mock)

    @patch("samcli.commands._utils.iac_validations.click")
    def test_validation_success_cdk_require_stack(self, click_mock):
        params = {"project_type": "CDK", "cdk_app": "foo", "stack_name": "stack"}
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        click_mock.get_current_context.return_value = context_mock
        click_mock.BadOptionUsage = click.BadOptionUsage

        project_mock = Mock()
        stack_mock = Mock()
        stack_mock.name = "stack"
        project_mock.stacks = [stack_mock]

        self.func_require_stack(project=project_mock)

    @patch("samcli.commands._utils.iac_validations.click")
    def test_validation_success_cdk_no_need_to_specify_stack_name(self, click_mock):
        params = {
            "project_type": "CDK",
            "cdk_app": "foo",
        }
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        click_mock.get_current_context.return_value = context_mock
        click_mock.BadOptionUsage = click.BadOptionUsage

        project_mock = Mock()
        stack_mock = Mock()
        stack_mock.name = "stack"
        project_mock.stacks = [stack_mock]

        self.func_require_stack(project=project_mock)

    @patch("samcli.commands._utils.iac_validations.click")
    def test_validation_fail_cdk_missing_stack_name(self, click_mock):
        params = {
            "project_type": "CDK",
            "cdk_app": "foo",
        }
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        click_mock.get_current_context.return_value = context_mock
        click_mock.BadOptionUsage = click.BadOptionUsage

        project_mock = Mock()
        project_mock.stacks = [Mock(), Mock()]

        with self.assertRaises(click_mock.BadOptionUsage) as ex:
            self.func_require_stack(project=project_mock)
        self.assertEqual(ex.exception.option_name, "--stack-name")
        self.assertEqual(ex.exception.message, "More than one stack found. Use '--stack-name' to specify the stack.")

    @patch("samcli.commands._utils.iac_validations.click")
    def test_validation_fail_cdk_not_found_stack_name(self, click_mock):
        params = {"project_type": "CDK", "cdk_app": "foo", "stack_name": "non_existent_stack"}
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        click_mock.get_current_context.return_value = context_mock
        click_mock.BadOptionUsage = click.BadOptionUsage

        project_mock = Mock()
        stack_mock = Mock()
        stack_mock.name = "stack"
        project_mock.stacks = [stack_mock]
        project_mock.find_stack_by_name.return_value = None

        with self.assertRaises(click_mock.BadOptionUsage) as ex:
            self.func_require_stack(project=project_mock)
        self.assertEqual(ex.exception.option_name, "--stack-name")
        self.assertEqual(ex.exception.message, "Stack with stack name 'non_existent_stack' not found.")
