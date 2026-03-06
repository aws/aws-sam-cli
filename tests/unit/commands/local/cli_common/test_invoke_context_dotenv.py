"""
Unit tests for .env file support in InvokeContext
"""

import tempfile
import os
from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.commands.local.cli_common.invoke_context import InvokeContext


class TestInvokeContext_DotenvMerging(TestCase):
    """Tests for merging .env files with JSON env vars"""

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_dotenv_only(self, MockFunctionProvider, MockStackProvider, MockGetContainerManager):
        """Should load only .env file when JSON is not provided"""
        # Create .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("VAR1=from_dotenv\n")
            f.write("VAR2=also_from_dotenv\n")
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

            # Mock container manager to avoid Docker checks
            mock_container_manager = Mock()
            mock_container_manager.is_docker_reachable = True
            MockGetContainerManager.return_value = mock_container_manager

            with InvokeContext(template_file=template_path, dotenv_file=dotenv_path, env_vars_file=None) as context:
                # Check that env vars were loaded correctly
                self.assertIsNotNone(context._env_vars_value)
                self.assertIn("Parameters", context._env_vars_value)
                self.assertEqual(context._env_vars_value["Parameters"]["VAR1"], "from_dotenv")
                self.assertEqual(context._env_vars_value["Parameters"]["VAR2"], "also_from_dotenv")
        finally:
            os.unlink(dotenv_path)
            os.unlink(template_path)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_json_only(self, MockFunctionProvider, MockStackProvider, MockGetContainerManager):
        """Should load only JSON file when .env is not provided"""
        # Create JSON env vars file
        import json

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"Parameters": {"VAR1": "from_json", "VAR2": "also_from_json"}}, f)
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

            # Mock container manager to avoid Docker checks
            mock_container_manager = Mock()
            mock_container_manager.is_docker_reachable = True
            MockGetContainerManager.return_value = mock_container_manager

            with InvokeContext(template_file=template_path, dotenv_file=None, env_vars_file=json_path) as context:
                # Check that env vars were loaded correctly
                self.assertIsNotNone(context._env_vars_value)
                self.assertIn("Parameters", context._env_vars_value)
                self.assertEqual(context._env_vars_value["Parameters"]["VAR1"], "from_json")
                self.assertEqual(context._env_vars_value["Parameters"]["VAR2"], "also_from_json")
        finally:
            os.unlink(json_path)
            os.unlink(template_path)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_json_overrides_dotenv(self, MockFunctionProvider, MockStackProvider, MockGetContainerManager):
        """Should have JSON values override .env values when both are provided"""
        # Create .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("VAR1=from_dotenv\n")
            f.write("VAR2=also_from_dotenv\n")
            f.write("VAR3=only_in_dotenv\n")
            dotenv_path = f.name

        # Create JSON env vars file (overriding VAR1 and VAR2)
        import json

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"Parameters": {"VAR1": "from_json_override", "VAR2": "also_from_json_override"}}, f)
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

            # Mock container manager to avoid Docker checks
            mock_container_manager = Mock()
            mock_container_manager.is_docker_reachable = True
            MockGetContainerManager.return_value = mock_container_manager

            with InvokeContext(
                template_file=template_path, dotenv_file=dotenv_path, env_vars_file=json_path
            ) as context:
                # Check that env vars were merged with JSON taking precedence
                self.assertIsNotNone(context._env_vars_value)
                self.assertIn("Parameters", context._env_vars_value)

                # JSON should override dotenv
                self.assertEqual(context._env_vars_value["Parameters"]["VAR1"], "from_json_override")
                self.assertEqual(context._env_vars_value["Parameters"]["VAR2"], "also_from_json_override")

                # Dotenv-only value should still be present
                self.assertEqual(context._env_vars_value["Parameters"]["VAR3"], "only_in_dotenv")
        finally:
            os.unlink(dotenv_path)
            os.unlink(json_path)
            os.unlink(template_path)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_function_specific_overrides_preserved(
        self, MockFunctionProvider, MockStackProvider, MockGetContainerManager
    ):
        """Should preserve function-specific overrides from JSON"""
        # Create .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("GLOBAL_VAR=from_dotenv\n")
            dotenv_path = f.name

        # Create JSON with function-specific overrides
        import json

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "Parameters": {"GLOBAL_VAR": "global_override"},
                    "MyFunction": {"FUNCTION_SPECIFIC": "function_value"},
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

            # Mock container manager to avoid Docker checks
            mock_container_manager = Mock()
            mock_container_manager.is_docker_reachable = True
            MockGetContainerManager.return_value = mock_container_manager

            with InvokeContext(
                template_file=template_path, dotenv_file=dotenv_path, env_vars_file=json_path
            ) as context:
                # Check that both global and function-specific overrides are preserved
                self.assertIsNotNone(context._env_vars_value)
                self.assertIn("Parameters", context._env_vars_value)
                self.assertIn("MyFunction", context._env_vars_value)

                self.assertEqual(context._env_vars_value["Parameters"]["GLOBAL_VAR"], "global_override")
                self.assertEqual(context._env_vars_value["MyFunction"]["FUNCTION_SPECIFIC"], "function_value")
        finally:
            os.unlink(dotenv_path)
            os.unlink(json_path)
            os.unlink(template_path)


class TestInvokeContext_ContainerDotenvMerging(TestCase):
    """Tests for container dotenv functionality"""

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_container_dotenv_only(self, MockFunctionProvider, MockStackProvider, MockGetContainerManager):
        """Should load container env vars from .env file only"""
        # Create container .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("DEBUG_VAR=debug_value\n")
            f.write("CONTAINER_VAR=container_value\n")
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

            # Mock container manager to avoid Docker checks
            mock_container_manager = Mock()
            mock_container_manager.is_docker_reachable = True
            MockGetContainerManager.return_value = mock_container_manager

            with InvokeContext(
                template_file=template_path, container_dotenv_file=container_dotenv_path, container_env_vars_file=None
            ) as context:
                # Check that container env vars were loaded correctly
                # Container env vars should remain flat (not wrapped in Parameters)
                self.assertIsNotNone(context._container_env_vars_value)
                self.assertEqual(context._container_env_vars_value["DEBUG_VAR"], "debug_value")
                self.assertEqual(context._container_env_vars_value["CONTAINER_VAR"], "container_value")
                # Should NOT have Parameters wrapper
                self.assertNotIn("Parameters", context._container_env_vars_value)
        finally:
            os.unlink(container_dotenv_path)
            os.unlink(template_path)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_container_json_overrides_container_dotenv(
        self, MockFunctionProvider, MockStackProvider, MockGetContainerManager
    ):
        """Should have container JSON values override container .env values"""
        # Create container .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("VAR1=from_container_dotenv\n")
            f.write("VAR2=also_from_container_dotenv\n")
            f.write("VAR3=only_in_container_dotenv\n")
            container_dotenv_path = f.name

        # Create container JSON env vars file (overriding VAR1 and VAR2)
        import json

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"VAR1": "from_container_json", "VAR2": "also_from_container_json"}, f)
            container_json_path = f.name

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

            # Mock container manager to avoid Docker checks
            mock_container_manager = Mock()
            mock_container_manager.is_docker_reachable = True
            MockGetContainerManager.return_value = mock_container_manager

            with InvokeContext(
                template_file=template_path,
                container_dotenv_file=container_dotenv_path,
                container_env_vars_file=container_json_path,
            ) as context:
                # Check that container env vars were merged with JSON taking precedence
                self.assertIsNotNone(context._container_env_vars_value)

                # JSON should override dotenv
                self.assertEqual(context._container_env_vars_value["VAR1"], "from_container_json")
                self.assertEqual(context._container_env_vars_value["VAR2"], "also_from_container_json")

                # Dotenv-only value should still be present
                self.assertEqual(context._container_env_vars_value["VAR3"], "only_in_container_dotenv")

                # Should remain flat (no Parameters wrapper)
                self.assertNotIn("Parameters", context._container_env_vars_value)
        finally:
            os.unlink(container_dotenv_path)
            os.unlink(container_json_path)
            os.unlink(template_path)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_dotenv_and_container_dotenv_independent(
        self, MockFunctionProvider, MockStackProvider, MockGetContainerManager
    ):
        """Should handle both regular dotenv and container dotenv independently"""
        # Create regular .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("LAMBDA_VAR=lambda_value\n")
            dotenv_path = f.name

        # Create container .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("DEBUG_VAR=debug_value\n")
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

            # Mock container manager to avoid Docker checks
            mock_container_manager = Mock()
            mock_container_manager.is_docker_reachable = True
            MockGetContainerManager.return_value = mock_container_manager

            with InvokeContext(
                template_file=template_path, dotenv_file=dotenv_path, container_dotenv_file=container_dotenv_path
            ) as context:
                # Check that regular env vars are wrapped in Parameters
                self.assertIsNotNone(context._env_vars_value)
                self.assertIn("Parameters", context._env_vars_value)
                self.assertEqual(context._env_vars_value["Parameters"]["LAMBDA_VAR"], "lambda_value")

                # Check that container env vars are flat (not wrapped)
                self.assertIsNotNone(context._container_env_vars_value)
                self.assertEqual(context._container_env_vars_value["DEBUG_VAR"], "debug_value")
                self.assertNotIn("Parameters", context._container_env_vars_value)
        finally:
            os.unlink(dotenv_path)
            os.unlink(container_dotenv_path)
            os.unlink(template_path)


class TestInvokeContext_DotenvErrorHandling(TestCase):
    """Tests for error handling and edge cases with .env files"""

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_non_existent_dotenv_file_raises_exception(
        self, MockFunctionProvider, MockStackProvider, MockGetContainerManager
    ):
        """Should raise exception when .env file doesn't exist"""
        from samcli.commands.local.cli_common.invoke_context import InvalidEnvironmentVariablesFileException

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

            # Attempt to use non-existent .env file
            with self.assertRaises(InvalidEnvironmentVariablesFileException) as context:
                with InvokeContext(
                    template_file=template_path, dotenv_file="/nonexistent/path/.env", env_vars_file=None
                ):
                    pass

            self.assertIn("not found", str(context.exception))
        finally:
            os.unlink(template_path)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext._get_container_manager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_empty_dotenv_file_logs_warning(self, MockFunctionProvider, MockStackProvider, MockGetContainerManager):
        """Should log warning when .env file is empty"""
        # Create empty .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            # Write nothing - empty file
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

            with InvokeContext(template_file=template_path, dotenv_file=dotenv_path, env_vars_file=None) as context:
                # Empty file should result in None or empty Parameters
                self.assertTrue(context._env_vars_value is None or context._env_vars_value.get("Parameters", {}) == {})
        finally:
            os.unlink(dotenv_path)
            os.unlink(template_path)

    def test_get_dotenv_values_static_method_nonexistent_file(self):
        """Test that _get_dotenv_values raises exception for non-existent file"""
        from samcli.commands.local.cli_common.invoke_context import (
            InvokeContext,
            InvalidEnvironmentVariablesFileException,
        )

        with self.assertRaises(InvalidEnvironmentVariablesFileException) as context:
            InvokeContext._get_dotenv_values("/path/that/does/not/exist/.env")

        self.assertIn("not found", str(context.exception))

    def test_get_dotenv_values_static_method_returns_none_for_none_input(self):
        """Test that _get_dotenv_values returns None when filename is None"""
        from samcli.commands.local.cli_common.invoke_context import InvokeContext

        result = InvokeContext._get_dotenv_values(None)
        self.assertIsNone(result)


class TestInvokeContext_MergeEnvVarsDirectTesting(TestCase):
    """Direct tests of _merge_env_vars without mocking - tests actual behavior"""

    def test_merge_with_both_none_returns_none(self):
        """Test that merging two None values returns None"""
        from samcli.commands.local.cli_common.invoke_context import InvokeContext

        result = InvokeContext._merge_env_vars(None, None, wrap_in_parameters=True)
        self.assertIsNone(result)

    def test_merge_dotenv_only_with_parameters_wrapping(self):
        """Test merging with only dotenv vars and Parameters wrapping"""
        from samcli.commands.local.cli_common.invoke_context import InvokeContext

        dotenv = {"VAR1": "value1", "VAR2": "value2"}
        result = InvokeContext._merge_env_vars(dotenv, None, wrap_in_parameters=True)

        self.assertIsNotNone(result)
        self.assertIn("Parameters", result)
        self.assertEqual(result["Parameters"]["VAR1"], "value1")
        self.assertEqual(result["Parameters"]["VAR2"], "value2")

    def test_merge_dotenv_only_without_parameters_wrapping(self):
        """Test merging with only dotenv vars without Parameters wrapping (container mode)"""
        from samcli.commands.local.cli_common.invoke_context import InvokeContext

        dotenv = {"VAR1": "value1", "VAR2": "value2"}
        result = InvokeContext._merge_env_vars(dotenv, None, wrap_in_parameters=False)

        self.assertIsNotNone(result)
        self.assertNotIn("Parameters", result)
        self.assertEqual(result["VAR1"], "value1")
        self.assertEqual(result["VAR2"], "value2")

    def test_merge_json_only_with_parameters(self):
        """Test merging with only JSON vars that have Parameters section"""
        from samcli.commands.local.cli_common.invoke_context import InvokeContext

        json_vars = {"Parameters": {"VAR1": "json_value1", "VAR2": "json_value2"}}
        result = InvokeContext._merge_env_vars(None, json_vars, wrap_in_parameters=True)

        self.assertIsNotNone(result)
        self.assertIn("Parameters", result)
        self.assertEqual(result["Parameters"]["VAR1"], "json_value1")
        self.assertEqual(result["Parameters"]["VAR2"], "json_value2")

    def test_merge_json_overrides_dotenv_in_parameters(self):
        """Test that JSON values override dotenv values in Parameters section"""
        from samcli.commands.local.cli_common.invoke_context import InvokeContext

        dotenv = {"VAR1": "dotenv_value", "VAR2": "dotenv_value2", "VAR3": "only_dotenv"}
        json_vars = {"Parameters": {"VAR1": "json_override", "VAR2": "json_override2"}}
        result = InvokeContext._merge_env_vars(dotenv, json_vars, wrap_in_parameters=True)

        self.assertIsNotNone(result)
        self.assertEqual(result["Parameters"]["VAR1"], "json_override")  # JSON wins
        self.assertEqual(result["Parameters"]["VAR2"], "json_override2")  # JSON wins
        self.assertEqual(result["Parameters"]["VAR3"], "only_dotenv")  # Dotenv preserved

    def test_merge_preserves_function_specific_overrides(self):
        """Test that function-specific JSON overrides are preserved alongside Parameters"""
        from samcli.commands.local.cli_common.invoke_context import InvokeContext

        dotenv = {"GLOBAL": "dotenv_value"}
        json_vars = {
            "Parameters": {"GLOBAL": "json_override"},
            "MyFunction": {"FUNC_VAR": "func_value"},
        }
        result = InvokeContext._merge_env_vars(dotenv, json_vars, wrap_in_parameters=True)

        self.assertIsNotNone(result)
        self.assertIn("Parameters", result)
        self.assertIn("MyFunction", result)
        self.assertEqual(result["Parameters"]["GLOBAL"], "json_override")
        self.assertEqual(result["MyFunction"]["FUNC_VAR"], "func_value")

    def test_merge_container_vars_without_parameters(self):
        """Test merging container vars (flat structure, no Parameters wrapping)"""
        from samcli.commands.local.cli_common.invoke_context import InvokeContext

        dotenv = {"DEBUG_VAR1": "debug1", "DEBUG_VAR2": "debug2"}
        json_vars = {"DEBUG_VAR1": "json_override", "DEBUG_VAR3": "json_only"}
        result = InvokeContext._merge_env_vars(dotenv, json_vars, wrap_in_parameters=False)

        self.assertIsNotNone(result)
        self.assertNotIn("Parameters", result)  # Should be flat
        self.assertEqual(result["DEBUG_VAR1"], "json_override")  # JSON wins
        self.assertEqual(result["DEBUG_VAR2"], "debug2")  # Dotenv preserved
        self.assertEqual(result["DEBUG_VAR3"], "json_only")  # JSON added
