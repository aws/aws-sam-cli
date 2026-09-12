"""Unit tests for OpenAPI generation context"""

import json
from io import StringIO
from unittest import TestCase
from unittest.mock import Mock, patch, mock_open, MagicMock

from samcli.commands.generate.openapi.context import OpenApiContext
from samcli.commands.generate.openapi.exceptions import GenerateOpenApiException


class TestOpenApiContext(TestCase):
    """Test OpenApiContext class"""

    def setUp(self):
        """Set up test fixtures"""
        self.template_file = "template.yaml"
        self.api_logical_id = "MyApi"
        self.output_file = "output.yaml"
        self.output_format = "yaml"
        self.parameter_overrides = {"Stage": "prod"}
        self.region = "us-east-1"
        self.profile = "default"

    def test_initialization(self):
        """Test context initialization"""
        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=self.api_logical_id,
            output_file=self.output_file,
            output_format=self.output_format,
            openapi_version="3.0",
            parameter_overrides=self.parameter_overrides,
            region=self.region,
            profile=self.profile,
        )

        self.assertEqual(context.template_file, self.template_file)
        self.assertEqual(context.api_logical_id, self.api_logical_id)
        self.assertEqual(context.output_file, self.output_file)
        self.assertEqual(context.output_format, self.output_format)
        self.assertEqual(context.parameter_overrides, self.parameter_overrides)
        self.assertEqual(context.region, self.region)
        self.assertEqual(context.profile, self.profile)

    def test_context_manager_enter(self):
        """Test context manager __enter__ returns self"""
        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=None,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        with context as ctx:
            self.assertIs(ctx, context)

    def test_context_manager_exit(self):
        """Test context manager __exit__ completes without error"""
        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=None,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        # Should not raise any exceptions
        with context:
            pass

    @patch("samcli.commands.generate.openapi.context.OpenApiGenerator")
    @patch("samcli.commands.generate.openapi.context.click")
    def test_run_successful_yaml_stdout(self, mock_click, mock_generator_class):
        """Test successful run with YAML output to stdout"""
        # Setup mock generator
        mock_generator = Mock()
        openapi_doc = {"openapi": "3.0.0", "info": {"title": "Test API"}}
        mock_generator.generate.return_value = openapi_doc
        mock_generator_class.return_value = mock_generator

        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=self.api_logical_id,
            output_file=None,  # stdout
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=self.parameter_overrides,
            region=self.region,
            profile=self.profile,
        )

        # Execute
        context.run()

        # Verify generator was created correctly
        mock_generator_class.assert_called_once_with(
            template_file=self.template_file,
            api_logical_id=self.api_logical_id,
            parameter_overrides=self.parameter_overrides,
            region=self.region,
            profile=self.profile,
        )

        # Verify generate was called
        mock_generator.generate.assert_called_once()

        # Verify output to stdout (click.echo called)
        mock_click.echo.assert_called_once()
        output = mock_click.echo.call_args[0][0]
        self.assertIn("openapi", output)

    @patch("samcli.commands.generate.openapi.context.OpenApiGenerator")
    @patch("samcli.commands.generate.openapi.context.click")
    @patch("builtins.open", new_callable=mock_open)
    def test_run_successful_yaml_file(self, mock_file, mock_click, mock_generator_class):
        """Test successful run with YAML output to file"""
        # Setup mock generator
        mock_generator = Mock()
        openapi_doc = {"openapi": "3.0.0", "info": {"title": "Test API"}}
        mock_generator.generate.return_value = openapi_doc
        mock_generator_class.return_value = mock_generator

        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=self.api_logical_id,
            output_file="api.yaml",
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=self.parameter_overrides,
            region=self.region,
            profile=self.profile,
        )

        # Execute
        context.run()

        # Verify file was opened for writing
        mock_file.assert_called_once_with("api.yaml", "w")

        # Verify content was written
        handle = mock_file()
        handle.write.assert_called()

        # Verify success message shown
        mock_click.secho.assert_called()
        success_msg = mock_click.secho.call_args[0][0]
        self.assertIn("Successfully generated", success_msg)
        self.assertIn("api.yaml", success_msg)

    @patch("samcli.commands.generate.openapi.context.OpenApiGenerator")
    @patch("samcli.commands.generate.openapi.context.click")
    def test_run_successful_json_stdout(self, mock_click, mock_generator_class):
        """Test successful run with JSON output to stdout"""
        # Setup mock generator
        mock_generator = Mock()
        openapi_doc = {"openapi": "3.0.0", "info": {"title": "Test API"}}
        mock_generator.generate.return_value = openapi_doc
        mock_generator_class.return_value = mock_generator

        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=self.api_logical_id,
            output_file=None,
            output_format="json",
            openapi_version="3.0",
            parameter_overrides=self.parameter_overrides,
            region=self.region,
            profile=self.profile,
        )

        # Execute
        context.run()

        # Verify output is JSON
        mock_click.echo.assert_called_once()
        output = mock_click.echo.call_args[0][0]
        # Should be valid JSON
        parsed = json.loads(output)
        self.assertEqual(parsed["openapi"], "3.0.0")

    @patch("samcli.commands.generate.openapi.context.OpenApiGenerator")
    def test_run_generator_exception(self, mock_generator_class):
        """Test run propagates GenerateOpenApiException"""
        # Setup mock generator that raises exception
        mock_generator = Mock()
        mock_generator.generate.side_effect = GenerateOpenApiException("API not found")
        mock_generator_class.return_value = mock_generator

        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=self.api_logical_id,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        # Execute and verify exception is propagated
        with self.assertRaises(GenerateOpenApiException) as ex:
            context.run()

        self.assertIn("API not found", str(ex.exception))

    @patch("samcli.commands.generate.openapi.context.OpenApiGenerator")
    def test_run_unexpected_exception(self, mock_generator_class):
        """Test run wraps unexpected exceptions"""
        # Setup mock generator that raises unexpected exception
        mock_generator = Mock()
        mock_generator.generate.side_effect = RuntimeError("Unexpected error")
        mock_generator_class.return_value = mock_generator

        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=None,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        # Execute and verify exception is wrapped
        with self.assertRaises(GenerateOpenApiException) as ex:
            context.run()

        self.assertIn("Unexpected error", str(ex.exception))

    def test_format_output_yaml(self):
        """Test YAML output formatting"""
        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=None,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        openapi_doc = {"openapi": "3.0.0", "info": {"title": "Test API"}}
        output = context._format_output(openapi_doc)

        # Should be YAML format
        self.assertIsInstance(output, str)
        self.assertIn("openapi:", output)
        self.assertIn("3.0.0", output)

    def test_format_output_json(self):
        """Test JSON output formatting"""
        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=None,
            output_file=None,
            output_format="json",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        openapi_doc = {"openapi": "3.0.0", "info": {"title": "Test API"}}
        output = context._format_output(openapi_doc)

        # Should be valid JSON
        self.assertIsInstance(output, str)
        parsed = json.loads(output)
        self.assertEqual(parsed["openapi"], "3.0.0")
        self.assertEqual(parsed["info"]["title"], "Test API")

    @patch("builtins.open", new_callable=mock_open)
    def test_write_output_to_file(self, mock_file):
        """Test writing output to file"""
        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=None,
            output_file="output.yaml",
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        content = "openapi: 3.0.0\n"
        context._write_output(content)

        # Verify file operations
        mock_file.assert_called_once_with("output.yaml", "w")
        handle = mock_file()
        handle.write.assert_called_once_with(content)

    @patch("samcli.commands.generate.openapi.context.click")
    def test_write_output_to_stdout(self, mock_click):
        """Test writing output to stdout"""
        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=None,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        content = "openapi: 3.0.0\n"
        context._write_output(content)

        # Verify click.echo was called
        mock_click.echo.assert_called_once_with(content)

    @patch("builtins.open", side_effect=IOError("Permission denied"))
    def test_write_output_file_error(self, mock_file):
        """Test file write error handling"""
        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=None,
            output_file="output.yaml",
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        content = "openapi: 3.0.0\n"

        # Verify exception is raised
        with self.assertRaises(GenerateOpenApiException) as ex:
            context._write_output(content)

        self.assertIn("Failed to write to file", str(ex.exception))
        self.assertIn("output.yaml", str(ex.exception))

    @patch("samcli.commands.generate.openapi.context.click")
    def test_display_success_with_file(self, mock_click):
        """Test success message when writing to file"""
        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=None,
            output_file="api.yaml",
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        context._display_success()

        # Verify success message shown with file info
        mock_click.secho.assert_called_once()
        message = mock_click.secho.call_args[0][0]
        self.assertIn("Successfully generated", message)
        self.assertIn("api.yaml", message)
        self.assertEqual(mock_click.secho.call_args[1]["fg"], "green")

    @patch("samcli.commands.generate.openapi.context.click")
    def test_display_success_without_file(self, mock_click):
        """Test success message when writing to stdout"""
        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=None,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        context._display_success()

        # Should not display message when output is stdout
        # (to avoid cluttering piped output)
        mock_click.secho.assert_not_called()

    @patch("samcli.commands.generate.openapi.context.OpenApiGenerator")
    @patch("samcli.commands.generate.openapi.context.click")
    def test_run_with_none_parameters(self, mock_click, mock_generator_class):
        """Test run with all optional parameters as None"""
        # Setup mock generator
        mock_generator = Mock()
        openapi_doc = {"openapi": "3.0.0"}
        mock_generator.generate.return_value = openapi_doc
        mock_generator_class.return_value = mock_generator

        context = OpenApiContext(
            template_file=self.template_file,
            api_logical_id=None,
            output_file=None,
            output_format="yaml",
            openapi_version="3.0",
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        # Should execute without errors
        context.run()

        # Verify generator was created with None values
        mock_generator_class.assert_called_once_with(
            template_file=self.template_file,
            api_logical_id=None,
            parameter_overrides=None,
            region=None,
            profile=None,
        )

        mock_generator.generate.assert_called_once()
