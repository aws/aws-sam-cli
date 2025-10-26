"""
Unit tests for function-specific environment variables in .env files
"""

import tempfile
import os
from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.commands.local.cli_common.invoke_context import InvokeContext


class TestParseFunctionSpecificEnvVars(TestCase):
    """Tests for _parse_function_specific_env_vars() method"""

    def test_parse_function_specific_basic(self):
        """Test basic function-specific parsing with asterisk separator"""
        env_dict = {
            "GLOBAL_VAR": "global_value",
            "MyFunction*API_KEY": "function_key",
            "MyFunction*TIMEOUT": "30",
        }

        result = InvokeContext._parse_function_specific_env_vars(env_dict)

        self.assertIn("Parameters", result)
        self.assertIn("MyFunction", result)
        self.assertEqual(result["Parameters"]["GLOBAL_VAR"], "global_value")
        self.assertEqual(result["MyFunction"]["API_KEY"], "function_key")
        self.assertEqual(result["MyFunction"]["TIMEOUT"], "30")

    def test_parse_all_caps_as_global(self):
        """Test that ALL_CAPS variables remain global"""
        env_dict = {
            "LAMBDA_VAR": "lambda_value",
            "AWS_REGION": "us-east-1",
            "API_KEY": "global_key",
        }

        result = InvokeContext._parse_function_specific_env_vars(env_dict)

        self.assertIn("Parameters", result)
        self.assertEqual(result["Parameters"]["LAMBDA_VAR"], "lambda_value")
        self.assertEqual(result["Parameters"]["AWS_REGION"], "us-east-1")
        self.assertEqual(result["Parameters"]["API_KEY"], "global_key")
        # No function-specific sections should be created
        self.assertEqual(len(result), 1)  # Only Parameters

    def test_parse_lowercase_as_global(self):
        """Test that lowercase_with_underscores remain global"""
        env_dict = {
            "database_url": "postgres://localhost",
            "api_version": "v1",
        }

        result = InvokeContext._parse_function_specific_env_vars(env_dict)

        self.assertIn("Parameters", result)
        self.assertEqual(result["Parameters"]["database_url"], "postgres://localhost")
        self.assertEqual(result["Parameters"]["api_version"], "v1")
        self.assertEqual(len(result), 1)  # Only Parameters

    def test_parse_any_naming_convention_with_asterisk(self):
        """Test that any naming convention works with asterisk separator"""
        env_dict = {
            "MyFunction*VAR1": "value1",  # PascalCase
            "myFunction*VAR2": "value2",  # camelCase
            "my_function*VAR3": "value3",  # snake_case
            "MYFUNCTION*VAR4": "value4",  # UPPERCASE
        }

        result = InvokeContext._parse_function_specific_env_vars(env_dict)

        self.assertIn("MyFunction", result)
        self.assertIn("myFunction", result)
        self.assertIn("my_function", result)
        self.assertIn("MYFUNCTION", result)
        self.assertEqual(result["MyFunction"]["VAR1"], "value1")
        self.assertEqual(result["myFunction"]["VAR2"], "value2")
        self.assertEqual(result["my_function"]["VAR3"], "value3")
        self.assertEqual(result["MYFUNCTION"]["VAR4"], "value4")

    def test_parse_mixed_variables(self):
        """Test parsing mixed global and function-specific variables"""
        env_dict = {
            "DATABASE_URL": "postgres://localhost",
            "MyFunction*API_KEY": "func_key",
            "LAMBDA_RUNTIME": "python3.11",
            "HelloWorld*TIMEOUT": "30",
            "API_VERSION": "v1",
            "MY_FUNCTION_VAR": "underscore_is_global",  # Underscore without asterisk = global
        }

        result = InvokeContext._parse_function_specific_env_vars(env_dict)

        # Check global vars
        self.assertEqual(result["Parameters"]["DATABASE_URL"], "postgres://localhost")
        self.assertEqual(result["Parameters"]["LAMBDA_RUNTIME"], "python3.11")
        self.assertEqual(result["Parameters"]["API_VERSION"], "v1")
        self.assertEqual(result["Parameters"]["MY_FUNCTION_VAR"], "underscore_is_global")

        # Check function-specific vars
        self.assertEqual(result["MyFunction"]["API_KEY"], "func_key")
        self.assertEqual(result["HelloWorld"]["TIMEOUT"], "30")

    def test_parse_no_underscore_is_global(self):
        """Test that variables without underscores are global"""
        env_dict = {
            "APIKEY": "key123",
            "DatabaseURL": "postgres://localhost",
            "timeout": "30",
        }

        result = InvokeContext._parse_function_specific_env_vars(env_dict)

        self.assertIn("Parameters", result)
        self.assertEqual(result["Parameters"]["APIKEY"], "key123")
        self.assertEqual(result["Parameters"]["DatabaseURL"], "postgres://localhost")
        self.assertEqual(result["Parameters"]["timeout"], "30")
        self.assertEqual(len(result), 1)  # Only Parameters

    def test_parse_multiple_vars_same_function(self):
        """Test multiple variables for the same function"""
        env_dict = {
            "MyFunction*VAR1": "value1",
            "MyFunction*VAR2": "value2",
            "MyFunction*VAR3": "value3",
        }

        result = InvokeContext._parse_function_specific_env_vars(env_dict)

        self.assertIn("MyFunction", result)
        self.assertEqual(len(result["MyFunction"]), 3)
        self.assertEqual(result["MyFunction"]["VAR1"], "value1")
        self.assertEqual(result["MyFunction"]["VAR2"], "value2")
        self.assertEqual(result["MyFunction"]["VAR3"], "value3")


class TestGetDotenvValuesWithParsing(TestCase):
    """Tests for _get_dotenv_values() with parse_function_specific parameter"""

    def test_parse_function_specific_false_returns_flat(self):
        """Test that parse_function_specific=False returns flat structure"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("GLOBAL_VAR=global\n")
            f.write("MyFunction*API_KEY=function_key\n")
            dotenv_path = f.name

        try:
            result = InvokeContext._get_dotenv_values(dotenv_path, parse_function_specific=False)

            # Should be flat
            self.assertNotIn("Parameters", result)
            self.assertNotIn("MyFunction", result)
            self.assertEqual(result["GLOBAL_VAR"], "global")
            self.assertEqual(result["MyFunction*API_KEY"], "function_key")
        finally:
            os.unlink(dotenv_path)

    def test_parse_function_specific_true_returns_hierarchical(self):
        """Test that parse_function_specific=True returns hierarchical structure"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("GLOBAL_VAR=global\n")
            f.write("MyFunction*API_KEY=function_key\n")
            dotenv_path = f.name

        try:
            result = InvokeContext._get_dotenv_values(dotenv_path, parse_function_specific=True)

            # Should be hierarchical
            self.assertIn("Parameters", result)
            self.assertIn("MyFunction", result)
            self.assertEqual(result["Parameters"]["GLOBAL_VAR"], "global")
            self.assertEqual(result["MyFunction"]["API_KEY"], "function_key")
        finally:
            os.unlink(dotenv_path)


class TestInvokeContextWithFunctionSpecific(TestCase):
    """Integration tests for InvokeContext with function-specific env vars"""

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_dotenv_with_function_specific_vars(self, MockFunctionProvider, MockStackProvider, MockGetContainerManager):
        """Test that function-specific vars from .env are properly loaded"""
        # Create .env file with function-specific vars
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("DATABASE_URL=postgres://localhost\n")
            f.write("MyFunction*API_KEY=my_function_key\n")
            f.write("MyFunction*DEBUG=true\n")
            f.write("HelloWorld*TIMEOUT=30\n")
            dotenv_path = f.name

        # Create dummy template
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("AWSTemplateFormatVersion: '2010-09-09'\n")
            template_path = f.name

        try:
            # Mock stack provider
            mock_stack = Mock()
            MockStackProvider.get_stacks.return_value = ([mock_stack], Mock())

            # Mock function provider
            mock_function_provider = Mock()
            mock_function_provider.get_all.return_value = []
            MockFunctionProvider.return_value = mock_function_provider

            # Mock container manager
            mock_container_manager = Mock()
            mock_container_manager.is_docker_reachable = True
            MockGetContainerManager.return_value = mock_container_manager

            with InvokeContext(template_file=template_path, dotenv_file=dotenv_path) as context:
                # Check hierarchical structure
                self.assertIsNotNone(context._env_vars_value)
                self.assertIn("Parameters", context._env_vars_value)
                self.assertIn("MyFunction", context._env_vars_value)
                self.assertIn("HelloWorld", context._env_vars_value)

                # Check global vars
                self.assertEqual(context._env_vars_value["Parameters"]["DATABASE_URL"], "postgres://localhost")

                # Check function-specific vars
                self.assertEqual(context._env_vars_value["MyFunction"]["API_KEY"], "my_function_key")
                self.assertEqual(context._env_vars_value["MyFunction"]["DEBUG"], "true")
                self.assertEqual(context._env_vars_value["HelloWorld"]["TIMEOUT"], "30")
        finally:
            os.unlink(dotenv_path)
            os.unlink(template_path)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_json_overrides_function_specific_dotenv(
        self, MockFunctionProvider, MockStackProvider, MockGetContainerManager
    ):
        """Test that JSON overrides function-specific vars from .env"""
        import json

        # Create .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("DATABASE_URL=from_dotenv\n")
            f.write("MyFunction*API_KEY=dotenv_key\n")
            f.write("MyFunction*DEBUG=true\n")
            dotenv_path = f.name

        # Create JSON file with overrides
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "Parameters": {"DATABASE_URL": "from_json"},
                    "MyFunction": {"API_KEY": "json_key"},  # Override function-specific
                },
                f,
            )
            json_path = f.name

        # Create dummy template
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("AWSTemplateFormatVersion: '2010-09-09'\n")
            template_path = f.name

        try:
            # Mock stack provider
            mock_stack = Mock()
            MockStackProvider.get_stacks.return_value = ([mock_stack], Mock())

            # Mock function provider
            mock_function_provider = Mock()
            mock_function_provider.get_all.return_value = []
            MockFunctionProvider.return_value = mock_function_provider

            # Mock container manager
            mock_container_manager = Mock()
            mock_container_manager.is_docker_reachable = True
            MockGetContainerManager.return_value = mock_container_manager

            with InvokeContext(
                template_file=template_path, dotenv_file=dotenv_path, env_vars_file=json_path
            ) as context:
                # Check that JSON overrode global var
                self.assertEqual(context._env_vars_value["Parameters"]["DATABASE_URL"], "from_json")

                # Check that JSON overrode function-specific var
                self.assertEqual(context._env_vars_value["MyFunction"]["API_KEY"], "json_key")

                # Check that non-overridden function-specific var remains
                self.assertEqual(context._env_vars_value["MyFunction"]["DEBUG"], "true")
        finally:
            os.unlink(dotenv_path)
            os.unlink(json_path)
            os.unlink(template_path)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_container_dotenv_remains_flat(self, MockFunctionProvider, MockStackProvider, MockGetContainerManager):
        """Test that container dotenv doesn't parse function-specific vars"""
        # Create container .env file with would-be function-specific vars
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("DEBUG_VAR=debug\n")
            f.write("MyFunction*API_KEY=key\n")  # Should stay flat (not parsed for containers)
            container_dotenv_path = f.name

        # Create dummy template
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("AWSTemplateFormatVersion: '2010-09-09'\n")
            template_path = f.name

        try:
            # Mock stack provider
            mock_stack = Mock()
            MockStackProvider.get_stacks.return_value = ([mock_stack], Mock())

            # Mock function provider
            mock_function_provider = Mock()
            mock_function_provider.get_all.return_value = []
            MockFunctionProvider.return_value = mock_function_provider

            # Mock container manager
            mock_container_manager = Mock()
            mock_container_manager.is_docker_reachable = True
            MockGetContainerManager.return_value = mock_container_manager

            with InvokeContext(template_file=template_path, container_dotenv_file=container_dotenv_path) as context:
                # Container env vars should remain flat
                self.assertIsNotNone(context._container_env_vars_value)
                self.assertNotIn("Parameters", context._container_env_vars_value)
                self.assertNotIn("MyFunction", context._container_env_vars_value)

                # Variables should be in flat structure
                self.assertEqual(context._container_env_vars_value["DEBUG_VAR"], "debug")
                self.assertEqual(context._container_env_vars_value["MyFunction*API_KEY"], "key")
        finally:
            os.unlink(container_dotenv_path)
            os.unlink(template_path)


class TestMergeEnvVarsWithHierarchical(TestCase):
    """Tests for _merge_env_vars with hierarchical dotenv structures"""

    def test_merge_hierarchical_dotenv_with_json(self):
        """Test merging hierarchical dotenv with JSON"""
        dotenv_vars = {
            "Parameters": {"GLOBAL1": "dotenv_global1", "GLOBAL2": "dotenv_global2"},
            "MyFunction": {"VAR1": "dotenv_func1"},
        }
        json_vars = {
            "Parameters": {"GLOBAL1": "json_global1"},  # Override
            "MyFunction": {"VAR2": "json_func2"},  # Add new
        }

        result = InvokeContext._merge_env_vars(dotenv_vars, json_vars, wrap_in_parameters=True)

        # Check global vars merge
        self.assertEqual(result["Parameters"]["GLOBAL1"], "json_global1")  # JSON wins
        self.assertEqual(result["Parameters"]["GLOBAL2"], "dotenv_global2")  # Preserved

        # Check function-specific merge
        self.assertEqual(result["MyFunction"]["VAR1"], "dotenv_func1")  # Preserved
        self.assertEqual(result["MyFunction"]["VAR2"], "json_func2")  # Added

    def test_merge_hierarchical_dotenv_only(self):
        """Test hierarchical dotenv without JSON"""
        dotenv_vars = {
            "Parameters": {"GLOBAL": "value"},
            "MyFunction": {"VAR": "func_value"},
        }

        result = InvokeContext._merge_env_vars(dotenv_vars, None, wrap_in_parameters=True)

        self.assertIn("Parameters", result)
        self.assertIn("MyFunction", result)
        self.assertEqual(result["Parameters"]["GLOBAL"], "value")
        self.assertEqual(result["MyFunction"]["VAR"], "func_value")
