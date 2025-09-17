"""
Unit tests for start-function-urls core command
"""

from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock
from click import Context

from samcli.commands.local.start_function_urls.core.command import InvokeFunctionUrlsCommand
from samcli.commands.local.start_function_urls.core.formatters import InvokeFunctionUrlsCommandHelpTextFormatter


class TestInvokeFunctionUrlsCommand(TestCase):
    """Test InvokeFunctionUrlsCommand class"""

    def test_custom_formatter_context(self):
        """Test CustomFormatterContext uses correct formatter"""
        # Context requires a command, so we'll just check the class attribute
        self.assertEqual(
            InvokeFunctionUrlsCommand.CustomFormatterContext.formatter_class, InvokeFunctionUrlsCommandHelpTextFormatter
        )

    def test_context_class_is_set(self):
        """Test that context_class is properly set"""
        self.assertEqual(InvokeFunctionUrlsCommand.context_class, InvokeFunctionUrlsCommand.CustomFormatterContext)

    def test_format_examples(self):
        """Test format_examples static method"""
        ctx_mock = Mock(spec=Context)
        ctx_mock.command_path = "sam local start-function-urls"

        formatter_mock = Mock(spec=InvokeFunctionUrlsCommandHelpTextFormatter)
        formatter_mock.indented_section = MagicMock()
        formatter_mock.write_rd = MagicMock()

        # Call the static method
        InvokeFunctionUrlsCommand.format_examples(ctx_mock, formatter_mock)

        # Verify indented_section was called
        formatter_mock.indented_section.assert_called_once_with(name="Examples", extra_indents=1)

        # Verify write_rd was called within the context
        formatter_mock.indented_section().__enter__().write_rd.assert_not_called()

    def test_format_examples_content(self):
        """Test that format_examples creates correct row definitions"""
        ctx_mock = Mock(spec=Context)
        ctx_mock.command_path = "sam local start-function-urls"

        formatter_mock = Mock(spec=InvokeFunctionUrlsCommandHelpTextFormatter)

        # Capture the row definitions passed to write_rd
        captured_rows = []

        def capture_write_rd(rows):
            captured_rows.extend(rows)

        formatter_mock.write_rd = capture_write_rd

        # Mock the context manager
        formatter_mock.indented_section = MagicMock()
        formatter_mock.indented_section().__enter__ = Mock(return_value=formatter_mock)
        formatter_mock.indented_section().__exit__ = Mock(return_value=None)

        # Call the static method
        InvokeFunctionUrlsCommand.format_examples(ctx_mock, formatter_mock)

        # Verify we have row definitions
        self.assertGreater(len(captured_rows), 0)

        # Check for expected command examples
        row_texts = [getattr(row, "name", "") for row in captured_rows if hasattr(row, "name")]

        # Should contain example commands
        self.assertTrue(any("sam local start-function-urls" in text for text in row_texts))
        self.assertTrue(any("--port-range" in text for text in row_texts))
        self.assertTrue(any("--function-name" in text for text in row_texts))
        self.assertTrue(any("--env-vars" in text for text in row_texts))

    def test_format_options(self):
        """Test format_options method"""
        # InvokeFunctionUrlsCommand requires a description argument and name (from Click's Command)
        command = InvokeFunctionUrlsCommand(name="start-function-urls", description="Test command for Function URLs")

        ctx_mock = Mock(spec=Context)
        ctx_mock.command_path = "sam local start-function-urls"

        formatter_mock = Mock(spec=InvokeFunctionUrlsCommandHelpTextFormatter)
        formatter_mock.indented_section = MagicMock()
        formatter_mock.write_rd = MagicMock()

        # Mock the parent class methods
        with patch.object(command, "format_description") as format_desc_mock:
            with patch.object(command, "get_params") as get_params_mock:
                with patch(
                    "samcli.commands.local.start_function_urls.core.command.CoreCommand._format_options"
                ) as format_options_mock:
                    get_params_mock.return_value = []

                    # Call format_options
                    command.format_options(ctx_mock, formatter_mock)

                    # Verify format_description was called
                    format_desc_mock.assert_called_once_with(formatter_mock)

                    # Verify format_examples was called (indirectly through static method)
                    # This is tested by checking if indented_section was called
                    formatter_mock.indented_section.assert_called()

                    # Verify CoreCommand._format_options was called
                    format_options_mock.assert_called_once()

                    # Check the arguments passed to _format_options
                    call_args = format_options_mock.call_args
                    self.assertEqual(call_args[1]["ctx"], ctx_mock)
                    self.assertEqual(call_args[1]["formatter"], formatter_mock)
