from unittest import TestCase
from unittest.mock import Mock

from samcli.commands.docs.command_context import DocsCommandContext
from samcli.commands.docs.core.command import DocsBaseCommand, DESCRIPTION, DocsSubCommand
from tests.unit.cli.test_command import MockFormatter


class TestDocsBaseCommand(TestCase):
    def test_formatter(self):
        ctx = Mock()
        ctx.command_path = "sam docs"
        formatter = MockFormatter(scrub_text=True)
        cmd = DocsBaseCommand(name="sync", requires_credentials=True, description=DESCRIPTION)
        cmd.format_options(ctx, formatter)
        formatting_result = formatter.data
        self.assertEqual(len(formatting_result), 2)
        description = formatting_result.get("Description", {})
        commands = formatting_result.get("Commands", {})
        self.assertEqual(len(description), 1)
        self.assertIn(
            (
                "Launch the AWS SAM CLI documentation in a browser! "
                "This command will\n  show information about setting up credentials, "
                "the\n  AWS SAM CLI lifecycle and other useful details. \n\n  "
                "The command also be run with sub-commands to open specific pages."
            ),
            description[0][0],
        )
        self.assertEqual(len(commands), 20)
        all_commands = set(DocsCommandContext().get_complete_command_paths())
        formatter_commands = set([command[0] for command in commands])
        self.assertEqual(all_commands, formatter_commands)


class TestDocsSubCommand(TestCase):
    def test_get_command_with_sub_commands(self):
        command = ["local", "invoke"]
        sub_command = DocsSubCommand(command=command)
        resolved_command = sub_command.get_command(ctx=None, cmd_name="local")
        self.assertTrue(isinstance(resolved_command, DocsSubCommand))

    def test_get_command_with_base_command(self):
        command = ["local"]
        sub_command = DocsSubCommand(command=command)
        resolved_command = sub_command.get_command(ctx=None, cmd_name="local")
        self.assertTrue(isinstance(resolved_command, DocsBaseCommand))

    def test_list_commands(self):
        self.assertEqual(DocsCommandContext().all_commands, DocsSubCommand().list_commands(ctx=None))
