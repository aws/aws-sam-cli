"""Unit tests for generate openapi command entry point"""

from unittest import TestCase
from unittest.mock import Mock, patch, call

from samcli.commands.generate.openapi.command import do_cli
from samcli.commands.generate.openapi.exceptions import GenerateOpenApiException


class TestGenerateOpenApiCommand(TestCase):
    """Test generate openapi command entry point"""

    @patch("samcli.commands.generate.openapi.context.OpenApiContext")
    def test_do_cli_successful(self, mock_context_class):
        """Test successful command execution"""
        # Setup
        template_file = "template.yaml"
        api_logical_id = "MyApi"
        output_file = "output.yaml"
        output_format = "yaml"
        parameter_overrides = {"Stage": "prod"}
        region = "us-east-1"
        profile = "default"

        # Create mock context instance
        mock_context = Mock()
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Execute
        do_cli(
            template_file=template_file,
            api_logical_id=api_logical_id,
            output_file=output_file,
            output_format=output_format,
            openapi_version="3.0",
            parameter_overrides=parameter_overrides,
            region=region,
            profile=profile,
        )

        # Verify context was created with correct parameters
        mock_context_class.assert_called_once_with(
            template_file=template_file,
            api_logical_id=api_logical_id,
            output_file=output_file,
            output_format=output_format,
            openapi_version="3.0",
            parameter_overrides=parameter_overrides,
            region=region,
            profile=profile,
        )

        # Verify run was called
        mock_context.run.assert_called_once()

    @patch("samcli.commands.generate.openapi.context.OpenApiContext")
    def test_do_cli_with_minimal_parameters(self, mock_context_class):
        """Test command with only required parameters"""
        # Setup
        template_file = "template.yaml"
        mock_context = Mock()
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Execute
        do_cli(
            template_file=template_file,
            api_logical_id=None,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        # Verify context was created
        mock_context_class.assert_called_once_with(
            template_file=template_file,
            api_logical_id=None,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        # Verify run was called
        mock_context.run.assert_called_once()

    @patch("samcli.commands.generate.openapi.context.OpenApiContext")
    def test_do_cli_json_format(self, mock_context_class):
        """Test command with JSON output format"""
        # Setup
        template_file = "template.yaml"
        output_format = "json"
        mock_context = Mock()
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Execute
        do_cli(
            template_file=template_file,
            api_logical_id=None,
            output_file=None,
            output_format=output_format,
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        # Verify format was passed correctly
        self.assertEqual(mock_context_class.call_args[1]["output_format"], "json")
        mock_context.run.assert_called_once()

    @patch("samcli.commands.generate.openapi.context.OpenApiContext")
    def test_do_cli_with_output_file(self, mock_context_class):
        """Test command writing to output file"""
        # Setup
        template_file = "template.yaml"
        output_file = "api-spec.yaml"
        mock_context = Mock()
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Execute
        do_cli(
            template_file=template_file,
            api_logical_id=None,
            output_file=output_file,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        # Verify output file was passed
        self.assertEqual(mock_context_class.call_args[1]["output_file"], output_file)
        mock_context.run.assert_called_once()

    @patch("samcli.commands.generate.openapi.context.OpenApiContext")
    def test_do_cli_with_parameter_overrides(self, mock_context_class):
        """Test command with parameter overrides"""
        # Setup
        template_file = "template.yaml"
        parameter_overrides = {"Stage": "prod", "Environment": "production"}
        mock_context = Mock()
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Execute
        do_cli(
            template_file=template_file,
            api_logical_id=None,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=parameter_overrides,
            region=None,
            profile=None,
        )

        # Verify parameter overrides were passed
        self.assertEqual(mock_context_class.call_args[1]["parameter_overrides"], parameter_overrides)
        mock_context.run.assert_called_once()

    @patch("samcli.commands.generate.openapi.context.OpenApiContext")
    def test_do_cli_propagates_exceptions(self, mock_context_class):
        """Test that exceptions from context are propagated"""
        # Setup
        template_file = "template.yaml"
        mock_context = Mock()
        mock_context.run.side_effect = GenerateOpenApiException("Test error")
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Execute and verify exception is raised
        with self.assertRaises(GenerateOpenApiException) as ex:
            do_cli(
                template_file=template_file,
                api_logical_id=None,
                output_file=None,
                output_format="yaml",
                openapi_version="3.0",
                parameter_overrides=None,
                region=None,
                profile=None,
            )

        self.assertIn("Test error", str(ex.exception))

    @patch("samcli.commands.generate.openapi.context.OpenApiContext")
    def test_do_cli_context_manager_cleanup(self, mock_context_class):
        """Test that context manager properly enters and exits"""
        # Setup
        template_file = "template.yaml"
        mock_context = Mock()
        mock_context_class.return_value.__enter__.return_value = mock_context
        mock_context_class.return_value.__exit__ = Mock()

        # Execute
        do_cli(
            template_file=template_file,
            api_logical_id=None,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        # Verify context manager was used properly
        mock_context_class.return_value.__enter__.assert_called_once()
        mock_context_class.return_value.__exit__.assert_called_once()
