"""
Unit tests for parameter file loading functionality
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from samcli.lib.config.exceptions import FileParseException
from samcli.lib.config.parameter_loaders import ParameterFileLoader


class TestParameterFileLoader(unittest.TestCase):
    """Test cases for ParameterFileLoader class"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_is_file_url_valid(self):
        """Test identification of valid file URLs"""
        self.assertTrue(ParameterFileLoader.is_file_url("file://path/to/file.json"))
        self.assertTrue(ParameterFileLoader.is_file_url("file:///absolute/path/file.yaml"))
        self.assertTrue(ParameterFileLoader.is_file_url("file://./relative/path/file.env"))

    def test_is_file_url_invalid(self):
        """Test identification of invalid file URLs"""
        self.assertFalse(ParameterFileLoader.is_file_url("http://example.com/file.json"))
        self.assertFalse(ParameterFileLoader.is_file_url("https://example.com/file.json"))
        self.assertFalse(ParameterFileLoader.is_file_url("path/to/file.json"))
        self.assertFalse(ParameterFileLoader.is_file_url(""))
        self.assertFalse(ParameterFileLoader.is_file_url(None))

    def test_parse_file_url_unix_path(self):
        """Test parsing Unix-style file URLs"""
        url = "file:///path/to/file.json"
        result = ParameterFileLoader.parse_file_url(url)
        self.assertEqual(result, "/path/to/file.json")

    def test_parse_file_url_relative_path(self):
        """Test parsing relative file URLs"""
        url = "file://./relative/path/file.json"
        result = ParameterFileLoader.parse_file_url(url)
        self.assertEqual(result, "./relative/path/file.json")

    def test_parse_file_url_with_env_vars(self):
        """Test parsing file URLs with environment variables"""
        with patch.dict(os.environ, {'TEST_VAR': 'test_value'}, clear=False):
            url = "file://$TEST_VAR/file.json"
            result = ParameterFileLoader.parse_file_url(url)
            self.assertEqual(result, "test_value/file.json")

    def test_parse_file_url_invalid(self):
        """Test parsing invalid file URLs"""
        with self.assertRaises(ValueError):
            ParameterFileLoader.parse_file_url("http://example.com/file.json")

    def test_load_json_file_valid(self):
        """Test loading valid JSON parameter file"""
        json_data = {"param1": "value1", "param2": "value2", "param3": 123}
        json_file = self.temp_path / "params.json"
        json_file.write_text(json.dumps(json_data))

        result = ParameterFileLoader.load_from_file(str(json_file))
        self.assertEqual(result, json_data)

    def test_load_json_file_invalid(self):
        """Test loading invalid JSON parameter file"""
        json_file = self.temp_path / "invalid.json"
        json_file.write_text('{"invalid": json}')

        with self.assertRaises(FileParseException):
            ParameterFileLoader.load_from_file(str(json_file))

    def test_load_json_file_not_object(self):
        """Test loading JSON file that's not an object"""
        json_file = self.temp_path / "array.json"
        json_file.write_text('["not", "an", "object"]')

        with self.assertRaises(FileParseException):
            ParameterFileLoader.load_from_file(str(json_file))

    def test_load_yaml_file_valid(self):
        """Test loading valid YAML parameter file"""
        yaml_content = """
param1: value1
param2: value2
param3: 123
nested:
  key: nested_value
"""
        yaml_file = self.temp_path / "params.yaml"
        yaml_file.write_text(yaml_content)

        result = ParameterFileLoader.load_from_file(str(yaml_file))
        expected = {
            "param1": "value1",
            "param2": "value2", 
            "param3": 123,
            "nested": {"key": "nested_value"}
        }
        self.assertEqual(result, expected)

    def test_load_yaml_file_empty(self):
        """Test loading empty YAML file"""
        yaml_file = self.temp_path / "empty.yaml"
        yaml_file.write_text("")

        result = ParameterFileLoader.load_from_file(str(yaml_file))
        self.assertEqual(result, {})

    def test_load_yaml_file_invalid(self):
        """Test loading invalid YAML parameter file"""
        yaml_file = self.temp_path / "invalid.yaml"
        yaml_file.write_text("param1: value1\ninvalid yaml: [ unclosed")

        with self.assertRaises(FileParseException):
            ParameterFileLoader.load_from_file(str(yaml_file))

    def test_load_env_file_simple(self):
        """Test loading simple ENV parameter file"""
        env_content = """
# This is a comment
PARAM1=value1
PARAM2=value2
PARAM3=123
"""
        env_file = self.temp_path / "params.env"
        env_file.write_text(env_content)

        result = ParameterFileLoader.load_from_file(str(env_file))
        expected = {"PARAM1": "value1", "PARAM2": "value2", "PARAM3": "123"}
        self.assertEqual(result, expected)

    def test_load_env_file_quoted_values(self):
        """Test loading ENV file with quoted values"""
        env_content = '''
SIMPLE=value
QUOTED="quoted value with spaces"
MULTILINE="line1
line2
line3"
'''
        env_file = self.temp_path / "params.env"
        env_file.write_text(env_content)

        result = ParameterFileLoader.load_from_file(str(env_file))
        expected = {
            "SIMPLE": "value",
            "QUOTED": "quoted value with spaces",
            "MULTILINE": "line1\nline2\nline3"
        }
        self.assertEqual(result, expected)

    def test_load_env_file_malformed_multiline(self):
        """Test loading ENV file with malformed multiline value"""
        env_content = '''
PARAM1=value1
UNTERMINATED="unclosed quote
PARAM2=value2
'''
        env_file = self.temp_path / "params.env"
        env_file.write_text(env_content)

        with self.assertRaises(FileParseException):
            ParameterFileLoader.load_from_file(str(env_file))

    def test_load_from_file_unsupported_extension(self):
        """Test loading file with unsupported extension"""
        txt_file = self.temp_path / "params.txt"
        txt_file.write_text("some content")

        with self.assertRaises(FileParseException):
            ParameterFileLoader.load_from_file(str(txt_file))

    def test_load_from_file_not_found(self):
        """Test loading non-existent file"""
        non_existent = self.temp_path / "does_not_exist.json"

        with self.assertRaises(FileNotFoundError):
            ParameterFileLoader.load_from_file(str(non_existent))

    def test_load_from_file_directory(self):
        """Test loading directory instead of file"""
        directory = self.temp_path / "not_a_file"
        directory.mkdir()

        with self.assertRaises(FileParseException):
            ParameterFileLoader.load_from_file(str(directory))

    def test_resolve_parameter_files_direct_only(self):
        """Test resolving parameter overrides with direct parameters only"""
        param_string = "Key1=Value1 Key2=Value2"

        direct, file_params = ParameterFileLoader.resolve_parameter_files(param_string)

        expected_direct = {"Key1": "Value1", "Key2": "Value2"}
        self.assertEqual(direct, expected_direct)
        self.assertEqual(file_params, {})

    def test_resolve_parameter_files_file_only(self):
        """Test resolving parameter overrides with file parameters only"""
        json_data = {"FileParam1": "FileValue1", "FileParam2": "FileValue2"}
        json_file = self.temp_path / "params.json"
        json_file.write_text(json.dumps(json_data))

        param_string = f"file://{json_file}"

        direct, file_params = ParameterFileLoader.resolve_parameter_files(param_string)

        self.assertEqual(direct, {})
        self.assertEqual(file_params, json_data)

    def test_resolve_parameter_files_mixed(self):
        """Test resolving parameter overrides with mixed parameters"""
        json_data = {"FileParam": "FileValue"}
        json_file = self.temp_path / "params.json"
        json_file.write_text(json.dumps(json_data))

        param_string = f"DirectParam=DirectValue file://{json_file} AnotherParam=AnotherValue"

        direct, file_params = ParameterFileLoader.resolve_parameter_files(param_string)

        expected_direct = {"DirectParam": "DirectValue", "AnotherParam": "AnotherValue"}
        self.assertEqual(direct, expected_direct)
        self.assertEqual(file_params, json_data)

    def test_resolve_parameter_files_empty(self):
        """Test resolving empty parameter overrides"""
        direct, file_params = ParameterFileLoader.resolve_parameter_files("")
        self.assertEqual(direct, {})
        self.assertEqual(file_params, {})

        direct, file_params = ParameterFileLoader.resolve_parameter_files(None)
        self.assertEqual(direct, {})
        self.assertEqual(file_params, {})

    def test_resolve_parameter_files_invalid_file(self):
        """Test resolving parameter overrides with invalid file"""
        param_string = "file:///nonexistent/file.json"

        with self.assertRaises(FileNotFoundError):
            ParameterFileLoader.resolve_parameter_files(param_string)

    def test_expand_environment_variables(self):
        """Test expanding environment variables in parameter values"""
        with patch.dict(os.environ, {'TEST_VAR': 'expanded'}, clear=False):
            params = {
                "NoVar": "simple_value",
                "WithVar": "$TEST_VAR",
                "WithBraces": "${TEST_VAR}_suffix",
                "NonExistent": "$NON_EXISTENT_VAR",
                "NumericValue": 123
            }

            result = ParameterFileLoader.expand_environment_variables(params)

            expected = {
                "NoVar": "simple_value",
                "WithVar": "expanded",
                "WithBraces": "expanded_suffix",
                "NonExistent": "$NON_EXISTENT_VAR",  # Unexpanded if var doesn't exist
                "NumericValue": 123  # Non-string values unchanged
            }
            self.assertEqual(result, expected)

    @patch('samcli.lib.config.parameter_loaders.LOG')
    def test_resolve_parameter_files_logs_info(self, mock_log):
        """Test that file parameter loading logs info messages"""
        json_data = {"param": "value"}
        json_file = self.temp_path / "params.json"
        json_file.write_text(json.dumps(json_data))

        param_string = f"file://{json_file}"
        ParameterFileLoader.resolve_parameter_files(param_string)

        mock_log.info.assert_called_once()
        self.assertIn("Loaded 1 parameters from file", mock_log.info.call_args[0][0])

    @patch('samcli.lib.config.parameter_loaders.LOG')
    def test_resolve_parameter_files_logs_warning_invalid_format(self, mock_log):
        """Test that invalid parameter formats log warnings"""
        param_string = "ValidParam=Value InvalidFormat"

        direct, file_params = ParameterFileLoader.resolve_parameter_files(param_string)

        expected_direct = {"ValidParam": "Value"}
        self.assertEqual(direct, expected_direct)
        self.assertEqual(file_params, {})
        mock_log.warning.assert_called_once_with("Skipping invalid parameter format: InvalidFormat")


if __name__ == '__main__':
    unittest.main()