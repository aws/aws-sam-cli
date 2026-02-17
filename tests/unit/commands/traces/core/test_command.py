"""
Unit tests for traces command class
"""

from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.traces.core.command import TracesCommand


class TestTracesCommand(TestCase):
    def test_get_options_traces_command_text(self):
        ctx = Mock()
        ctx.command_path = "sam traces"
        formatter = Mock()
        formatter.write_rd = Mock()
        formatter.indented_section = Mock()

        # Set up the mock to track indented_section calls
        indented_sections = {}

        def mock_indented_section(name, extra_indents=0):
            mock_context = Mock()
            mock_context.__enter__ = Mock(return_value=mock_context)
            mock_context.__exit__ = Mock(return_value=False)
            indented_sections[name] = True
            return mock_context

        formatter.indented_section.side_effect = mock_indented_section

        # Call format_examples
        TracesCommand.format_examples(ctx, formatter)

        # Verify that the expected sections were created
        self.assertIn("Examples", indented_sections)
        self.assertIn("Fetch traces by ID", indented_sections)
        self.assertIn("Tail traces as they become available", indented_sections)

        # Verify write_rd was called (once for each example subsection)
        self.assertEqual(formatter.write_rd.call_count, 2)
