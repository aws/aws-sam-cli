
import yaml

from unittest import TestCase
from mock import patch, mock_open
from parameterized import parameterized, param

from samcli.commands._utils.template import get_template_data


class TestInvokeContext_get_template_data(TestCase):

    def test_must_raise_if_file_does_not_exist(self):
        filename = "filename"

        with self.assertRaises(ValueError) as exception_ctx:
            get_template_data(filename)

        ex = exception_ctx.exception
        self.assertEquals(str(ex), "Template file not found at {}".format(filename))

    @patch("samcli.commands._utils.template.yaml_parse")
    @patch("samcli.commands._utils.template.pathlib")
    def test_must_read_file_and_parse(self, pathlib_mock, yaml_parse_mock):
        filename = "filename"
        file_data = "contents of the file"
        parse_result = "parse result"

        pathlib_mock.Path.return_value.exists.return_value = True  # Fake that the file exists

        m = mock_open(read_data=file_data)
        yaml_parse_mock.return_value = parse_result

        with patch("samcli.commands._utils.template.open", m):
            result = get_template_data(filename)

            self.assertEquals(result, parse_result)

        m.assert_called_with(filename, 'r')
        yaml_parse_mock.assert_called_with(file_data)

    @parameterized.expand([
        param(ValueError()),
        param(yaml.YAMLError())
    ])
    @patch("samcli.commands._utils.template.yaml_parse")
    @patch("samcli.commands._utils.template.pathlib")
    def test_must_raise_on_parse_errors(self, exception, pathlib_mock, yaml_parse_mock):
        filename = "filename"
        file_data = "contents of the file"

        pathlib_mock.Path.return_value.exists.return_value = True  # Fake that the file exists

        m = mock_open(read_data=file_data)
        yaml_parse_mock.side_effect = exception

        with patch("samcli.commands._utils.template.open", m):

            with self.assertRaises(ValueError) as ex_ctx:
                get_template_data(filename)

            actual_exception = ex_ctx.exception
            self.assertTrue(str(actual_exception).startswith("Failed to parse template: "))
