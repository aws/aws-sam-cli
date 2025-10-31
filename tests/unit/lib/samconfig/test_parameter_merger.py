"""
Unit tests for parameter merger functionality
"""

import unittest
from unittest.mock import patch

from samcli.lib.config.parameter_merger import ParameterMerger


class TestParameterMerger(unittest.TestCase):
    """Test cases for ParameterMerger class"""

    def test_merge_parameters_config_only(self):
        """Test merging with only config parameters"""
        config_params = {"Param1": "ConfigValue1", "Param2": "ConfigValue2"}

        result = ParameterMerger.merge_parameters(config_params=config_params)

        expected = {"Param1": "ConfigValue1", "Param2": "ConfigValue2"}
        self.assertEqual(result, expected)

    def test_merge_parameters_cli_only(self):
        """Test merging with only CLI parameters"""
        cli_params = {"Param1": "CLIValue1", "Param2": "CLIValue2"}

        result = ParameterMerger.merge_parameters(cli_params=cli_params)

        expected = {"Param1": "CLIValue1", "Param2": "CLIValue2"}
        self.assertEqual(result, expected)

    def test_merge_parameters_file_only(self):
        """Test merging with only file parameters"""
        file_params = {"Param1": "FileValue1", "Param2": "FileValue2"}

        result = ParameterMerger.merge_parameters(file_params=file_params)

        expected = {"Param1": "FileValue1", "Param2": "FileValue2"}
        self.assertEqual(result, expected)

    def test_merge_parameters_precedence(self):
        """Test parameter precedence: CLI > file > config"""
        config_params = {"Param1": "ConfigValue", "Param2": "ConfigValue", "Param3": "ConfigValue"}
        file_params = {"Param2": "FileValue", "Param3": "FileValue"}
        cli_params = {"Param3": "CLIValue"}

        result = ParameterMerger.merge_parameters(
            config_params=config_params, cli_params=cli_params, file_params=file_params
        )

        expected = {
            "Param1": "ConfigValue",  # Only in config
            "Param2": "FileValue",  # File overrides config
            "Param3": "CLIValue",  # CLI overrides both
        }
        self.assertEqual(result, expected)

    def test_merge_parameters_empty_inputs(self):
        """Test merging with empty/None inputs"""
        result = ParameterMerger.merge_parameters()
        self.assertEqual(result, {})

        result = ParameterMerger.merge_parameters(config_params={}, cli_params=None, file_params={})
        self.assertEqual(result, {})

    def test_merge_tags_config_only(self):
        """Test merging with only config tags"""
        config_tags = {"Environment": "prod", "Project": "MyApp"}

        result = ParameterMerger.merge_tags(config_tags=config_tags)

        expected = {"Environment": "prod", "Project": "MyApp"}
        self.assertEqual(result, expected)

    def test_merge_tags_precedence(self):
        """Test tag precedence: CLI > file > config"""
        config_tags = {"Environment": "config", "Project": "config", "CostCenter": "config"}
        file_tags = {"Project": "file", "CostCenter": "file"}
        cli_tags = {"CostCenter": "cli"}

        result = ParameterMerger.merge_tags(config_tags=config_tags, cli_tags=cli_tags, file_tags=file_tags)

        expected = {
            "Environment": "config",  # Only in config
            "Project": "file",  # File overrides config
            "CostCenter": "cli",  # CLI overrides both
        }
        self.assertEqual(result, expected)

    def test_format_for_cloudformation(self):
        """Test formatting parameters for CloudFormation"""
        parameters = {
            "StringParam": "value",
            "NumberParam": 42,
            "BooleanParam": True,
            "NullParam": None,
            "DictParam": {"key": "value"},
            "ListParam": [1, 2, 3],
        }

        result = ParameterMerger.format_for_cloudformation(parameters)

        expected = {
            "StringParam": "value",
            "NumberParam": "42",
            "BooleanParam": "True",
            "NullParam": "",
            "DictParam": '{"key": "value"}',
            "ListParam": "[1, 2, 3]",
        }
        self.assertEqual(result, expected)

    def test_format_for_cloudformation_empty(self):
        """Test formatting empty parameters"""
        result = ParameterMerger.format_for_cloudformation({})
        self.assertEqual(result, {})

        result = ParameterMerger.format_for_cloudformation(None)
        self.assertEqual(result, {})

    def test_parse_legacy_parameter_string_simple(self):
        """Test parsing simple parameter strings"""
        param_string = "Key1=Value1 Key2=Value2"

        result = ParameterMerger.parse_legacy_parameter_string(param_string)

        expected = {"Key1": "Value1", "Key2": "Value2"}
        self.assertEqual(result, expected)

    def test_parse_legacy_parameter_string_quoted(self):
        """Test parsing parameter strings with quoted values"""
        param_string = 'Key1="Value with spaces" Key2=SimpleValue'

        result = ParameterMerger.parse_legacy_parameter_string(param_string)

        expected = {"Key1": "Value with spaces", "Key2": "SimpleValue"}
        self.assertEqual(result, expected)

    def test_parse_legacy_parameter_string_complex(self):
        """Test parsing complex parameter strings"""
        param_string = 'DBHost=localhost DBPort=5432 DBName="my database" ConnectionString="host=localhost;port=5432"'

        result = ParameterMerger.parse_legacy_parameter_string(param_string)

        expected = {
            "DBHost": "localhost",
            "DBPort": "5432",
            "DBName": "my database",
            "ConnectionString": "host=localhost;port=5432",
        }
        self.assertEqual(result, expected)

    def test_parse_legacy_parameter_string_empty(self):
        """Test parsing empty/invalid parameter strings"""
        self.assertEqual(ParameterMerger.parse_legacy_parameter_string(""), {})
        self.assertEqual(ParameterMerger.parse_legacy_parameter_string(None), {})
        self.assertEqual(ParameterMerger.parse_legacy_parameter_string("   "), {})

    @patch("samcli.lib.config.parameter_merger.LOG")
    def test_parse_legacy_parameter_string_invalid_format(self, mock_log):
        """Test parsing parameter strings with invalid format"""
        param_string = "ValidKey=ValidValue InvalidEntry AnotherKey=AnotherValue"

        result = ParameterMerger.parse_legacy_parameter_string(param_string)

        expected = {"ValidKey": "ValidValue", "AnotherKey": "AnotherValue"}
        self.assertEqual(result, expected)
        mock_log.warning.assert_called_once()

    def test_validate_parameters_with_template(self):
        """Test parameter validation against template parameters"""
        parameters = {"ValidParam1": "value1", "ValidParam2": "value2", "InvalidParam": "invalid"}
        template_parameters = {"ValidParam1": {"Type": "String"}, "ValidParam2": {"Type": "String"}}

        result = ParameterMerger.validate_parameters(parameters, template_parameters)

        expected = {"ValidParam1": "value1", "ValidParam2": "value2"}
        self.assertEqual(result, expected)

    def test_validate_parameters_without_template(self):
        """Test parameter validation without template parameters"""
        parameters = {"Param1": "value1", "Param2": "value2"}

        result = ParameterMerger.validate_parameters(parameters, None)

        self.assertEqual(result, parameters)

    @patch("samcli.lib.config.parameter_merger.LOG")
    def test_validate_parameters_logs_warnings(self, mock_log):
        """Test parameter validation logs warnings for invalid parameters"""
        parameters = {"InvalidParam": "value"}
        template_parameters = {"ValidParam": {"Type": "String"}}

        result = ParameterMerger.validate_parameters(parameters, template_parameters)

        self.assertEqual(result, {})
        mock_log.warning.assert_called_once_with("Parameter 'InvalidParam' not found in template parameters. Skipping.")


if __name__ == "__main__":
    unittest.main()
