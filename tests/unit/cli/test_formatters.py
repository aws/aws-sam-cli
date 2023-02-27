from unittest import TestCase
from unittest.mock import patch, call
from samcli.cli.root.command_list import SAM_CLI_COMMANDS
from samcli.cli.formatters import (
    RowDefinition,
    RootCommandHelpTextFormatter,
)
from samcli.cli.row_modifiers import HighlightNewRowNameModifier


class TestRootCommandHelpTextFormatter(TestCase):
    def setUp(self):
        self.formatter = RootCommandHelpTextFormatter()

    def test_write_usage(self):
        prog = "sam"
        args = "validate"
        prefix = "usage: "
        expected_output = [
            call(f"usage: \x1b[1m{prog}\x1b[0m {args}"),
            call("\n"),
        ]
        with patch.object(self.formatter, "write") as mock_write:
            self.formatter.write_usage(prog, args, prefix)
            self.assertEqual(mock_write.call_args_list, expected_output)

    def test_write_heading(self):
        heading = "Command Options:"
        expected_output = [call(f"\x1b[1m{heading}\x1b[0m:\n")]
        with patch.object(self.formatter, "write") as mock_write:
            self.formatter.write_heading(heading)
            self.assertEqual(mock_write.call_args_list, expected_output)

    def test_write_rd_base(self):
        rows = [
            RowDefinition("init", "Initializes an AWS SAM project."),
            RowDefinition("build", "Builds an AWS SAM application."),
            RowDefinition("deploy", "Deploys an AWS SAM application."),
        ]

        expected_output = [
            call("init".ljust(self.formatter.left_justification_length)),
            call(" " * self.formatter.indent_increment),
            call("Initializes an AWS SAM project.\n"),
            call("build".ljust(self.formatter.left_justification_length)),
            call(" " * self.formatter.indent_increment),
            call("Builds an AWS SAM application.\n"),
            call("deploy".ljust(self.formatter.left_justification_length)),
            call(" " * self.formatter.indent_increment),
            call("Deploys an AWS SAM application.\n"),
        ]

        # Test with no new rows
        with patch.object(self.formatter, "write") as mock_write:
            self.formatter.write_rd(rows)
            self.assertEqual(mock_write.call_args_list, expected_output)

    def test_write_rd_with_modifiers(self):
        new_rows = [
            RowDefinition("new_cmd", "A new command.", extra_row_modifiers=[HighlightNewRowNameModifier()]),
        ]
        new_command = f"new_cmd {HighlightNewRowNameModifier.NEW_TEXT}".ljust(self.formatter.left_justification_length)
        expected_output_with_new = [
            call(f"\x1b[93m\x1b[1m{new_command}\x1b[0m"),
            call(" " * self.formatter.indent_increment),
            call("A new command.\n"),
        ]

        # Test with new rows
        with patch.object(self.formatter, "write") as mock_write:
            self.formatter.write_rd(new_rows)
            self.assertEqual(mock_write.call_args_list, expected_output_with_new)

    def test_section(self):
        name = "Section"
        expected_output = [call(f"\x1b[1m\x1b[1m\x1b[4m{name}\x1b[0m\x1b[0m:\n")]
        with patch.object(self.formatter, "write") as mock_write:
            with self.formatter.section(name):
                self.assertEqual(self.formatter.current_indent, self.formatter.indent_increment)
                pass
            self.assertEqual(mock_write.call_args_list, expected_output)
        self.assertEqual(self.formatter.current_indent, 0)

    def test_indented_section(self):
        name = "Section"
        with patch.object(self.formatter, "write") as mock_write:
            with self.formatter.indented_section(name, extra_indents=2):
                self.assertEqual(
                    self.formatter.current_indent,
                    self.formatter.indent_increment + (self.formatter.indent_increment * 2),
                )
            self.assertEqual(self.formatter.current_indent, 0)

    def test_left_justification_length(self):
        # Test that left_justification_length is set correctly in __init__
        expected_length = max(len(cmd) for cmd, _ in SAM_CLI_COMMANDS.items()) + self.formatter.ADDITIVE_JUSTIFICATION
        expected_length = min(expected_length, self.formatter.width // 2 - self.formatter.indent_increment)
        self.assertEqual(self.formatter.left_justification_length, expected_length)
