"""
Test the common CLI options for invoke
"""

import os

from unittest import TestCase
from mock import patch
from samcli.commands.local.cli_common.options import get_or_default_template_file_name, _TEMPLATE_OPTION_DEFAULT_VALUE


class TestGetOrDefaultTemplateFileName(TestCase):

    def test_must_return_abspath_of_user_provided_value(self):
        filename = "foo.txt"
        expected = os.path.abspath(filename)

        result = get_or_default_template_file_name(None, None, filename)
        self.assertEquals(result, expected)

    @patch("samcli.commands.local.cli_common.options.os")
    def test_must_return_yml_extension(self, os_mock):
        expected = "template.yml"

        os_mock.path.exists.return_value = False  # Fake .yaml file to not exist.
        os_mock.path.abspath.return_value = "absPath"

        result = get_or_default_template_file_name(None, None, _TEMPLATE_OPTION_DEFAULT_VALUE)
        self.assertEquals(result, "absPath")
        os_mock.path.abspath.assert_called_with(expected)

    @patch("samcli.commands.local.cli_common.options.os")
    def test_must_return_yaml_extension(self, os_mock):
        expected = "template.yaml"

        os_mock.path.exists.return_value = True
        os_mock.path.abspath.return_value = "absPath"

        result = get_or_default_template_file_name(None, None, _TEMPLATE_OPTION_DEFAULT_VALUE)
        self.assertEquals(result, "absPath")
        os_mock.path.abspath.assert_called_with(expected)
