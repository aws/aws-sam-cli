"""
Test the common CLI options
"""

import os

from unittest import TestCase
from unittest.mock import patch, MagicMock

import click

from samcli.commands._utils.options import (
    get_or_default_template_file_name,
    _TEMPLATE_OPTION_DEFAULT_VALUE,
    guided_deploy_stack_name,
)
from tests.unit.cli.test_cli_config_file import MockContext


class Mock:
    pass


class TestGetOrDefaultTemplateFileName(TestCase):
    def test_must_return_abspath_of_user_provided_value(self):
        filename = "foo.txt"
        expected = os.path.abspath(filename)

        result = get_or_default_template_file_name(None, None, filename, include_build=False)
        self.assertEqual(result, expected)

    @patch("samcli.commands._utils.options.os")
    def test_must_return_yml_extension(self, os_mock):
        expected = "template.yml"

        os_mock.path.exists.return_value = False  # Fake .yaml file to not exist.
        os_mock.path.abspath.return_value = "absPath"

        result = get_or_default_template_file_name(None, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=False)
        self.assertEqual(result, "absPath")
        os_mock.path.abspath.assert_called_with(expected)

    @patch("samcli.commands._utils.options.os")
    def test_must_return_yaml_extension(self, os_mock):
        expected = "template.yaml"

        os_mock.path.exists.return_value = True
        os_mock.path.abspath.return_value = "absPath"

        result = get_or_default_template_file_name(None, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=False)
        self.assertEqual(result, "absPath")
        os_mock.path.abspath.assert_called_with(expected)

    @patch("samcli.commands._utils.options.os")
    def test_must_return_built_template(self, os_mock):
        expected = os.path.join(".aws-sam", "build", "template.yaml")

        os_mock.path.exists.return_value = True
        os_mock.path.join = os.path.join  # Use the real method
        os_mock.path.abspath.return_value = "absPath"

        result = get_or_default_template_file_name(None, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=True)
        self.assertEqual(result, "absPath")
        os_mock.path.abspath.assert_called_with(expected)

    @patch("samcli.commands._utils.options.os")
    @patch("samcli.commands._utils.options.get_template_data")
    def test_verify_ctx(self, get_template_data_mock, os_mock):

        ctx = Mock()
        ctx.default_map = {}

        expected = os.path.join(".aws-sam", "build", "template.yaml")

        os_mock.path.exists.return_value = True
        os_mock.path.join = os.path.join  # Use the real method
        os_mock.path.abspath.return_value = "a/b/c/absPath"
        os_mock.path.dirname.return_value = "a/b/c"
        get_template_data_mock.return_value = "dummy_template_dict"

        result = get_or_default_template_file_name(ctx, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=True)
        self.assertEqual(result, "a/b/c/absPath")
        self.assertEqual(ctx.samconfig_dir, "a/b/c")
        self.assertEqual(ctx.template_dict, "dummy_template_dict")
        os_mock.path.abspath.assert_called_with(expected)

    def test_verify_ctx_template_file_param(self):

        ctx_mock = Mock()
        ctx_mock.default_map = {"template": "bar.txt"}
        expected_result_from_ctx = os.path.abspath("bar.txt")

        result = get_or_default_template_file_name(ctx_mock, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=True)
        self.assertEqual(result, expected_result_from_ctx)


class TestGuidedDeployStackName(TestCase):
    def test_must_return_provided_value_guided(self):
        stack_name = "provided-stack"
        mock_params = MagicMock()
        mock_params.get = MagicMock(return_value=True)
        result = guided_deploy_stack_name(
            ctx=MockContext(info_name="test", parent=None, params=mock_params),
            param=MagicMock(),
            provided_value=stack_name,
        )
        self.assertEqual(result, stack_name)

    def test_must_return_default_value_guided(self):
        stack_name = None
        mock_params = MagicMock()
        mock_params.get = MagicMock(return_value=True)
        result = guided_deploy_stack_name(
            ctx=MockContext(info_name="test", parent=None, params=mock_params),
            param=MagicMock(),
            provided_value=stack_name,
        )
        self.assertEqual(result, "sam-app")

    def test_must_return_provided_value_non_guided(self):
        stack_name = "provided-stack"
        mock_params = MagicMock()
        mock_params.get = MagicMock(return_value=False)
        result = guided_deploy_stack_name(ctx=MagicMock(), param=MagicMock(), provided_value=stack_name)
        self.assertEqual(result, "provided-stack")

    def test_exception_missing_parameter_no_value_non_guided(self):
        stack_name = None
        mock_params = MagicMock()
        mock_params.get = MagicMock(return_value=False)
        with self.assertRaises(click.BadOptionUsage):
            guided_deploy_stack_name(
                ctx=MockContext(info_name="test", parent=None, params=mock_params),
                param=MagicMock(),
                provided_value=stack_name,
            )
