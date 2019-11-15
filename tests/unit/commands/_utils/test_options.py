"""
Test the common CLI options
"""

import os

from unittest import TestCase
from unittest.mock import patch
from samcli.commands._utils.options import get_or_default_template_file_name, _TEMPLATE_OPTION_DEFAULT_VALUE


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
    def test_verify_ctx(self, os_mock):

        ctx = Mock()

        expected = os.path.join(".aws-sam", "build", "template.yaml")

        os_mock.path.exists.return_value = True
        os_mock.path.join = os.path.join  # Use the real method
        os_mock.path.abspath.return_value = "a/b/c/absPath"
        os_mock.path.dirname.return_value = "a/b/c/absPath"

        result = get_or_default_template_file_name(ctx, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=True)
        self.assertEqual(result, "a/b/c/absPath")
        self.assertEqual(ctx.config_path, "a/b/c/absPath")
        os_mock.path.abspath.assert_called_with(expected)
