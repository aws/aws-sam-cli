"""
CLI command for "docs" command
"""
import functools
import sys
from typing import List, Optional

import click
from click import Command, Context, style

from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.main import common_options, pass_context, print_cmdline_args
from samcli.cli.row_modifiers import BaseLineRowModifier, RowDefinition
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.exceptions import UserException
from samcli.lib.docs.browser_configuration import BrowserConfiguration, BrowserConfigurationError
from samcli.lib.docs.documentation import Documentation
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

COMMAND_NAME = "docs"
HELP_TEXT = "NEW! Open the documentation in a browser."
DESCRIPTION = """
  Launch the AWS SAM CLI documentation in a browser! This command will
  show information about setting up credentials, the
  AWS SAM CLI lifecycle and other useful details. 

  The command also be run with sub-commands to open specific pages.
"""

SUCCESS_MESSAGE = "Documentation page opened in a browser. These other sub-commands are also invokable."
ERROR_MESSAGE = "Failed to open a web browser. Use the following link to navigate to the documentation page: {URL}"


class InvalidDocsCommandException(UserException):
    """
    Exception when the docs command fails
    """


class DocsCommandHelpTextFormatter(RootCommandHelpTextFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.left_justification_length = self.width // 2 - self.indent_increment
        self.modifiers = [BaseLineRowModifier()]


class DocsBaseCommand(click.Command):
    class CustomFormatterContext(Context):
        formatter_class = DocsCommandHelpTextFormatter

    context_class = CustomFormatterContext

    def __init__(self, *args, **kwargs):
        self.docs_command = DocsCommand()
        command_callback = self.docs_command.command_callback
        super().__init__(name=COMMAND_NAME, help=HELP_TEXT, callback=command_callback)

    @staticmethod
    def format_description(formatter: DocsCommandHelpTextFormatter):
        with formatter.indented_section(name="Description", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        text="",
                        name=DESCRIPTION
                        + style("\n  This command does not require access to AWS credentials.", bold=True),
                    ),
                ],
            )

    def format_sub_commands(self, formatter: DocsCommandHelpTextFormatter):
        with formatter.indented_section(name="Commands", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(self.docs_command.base_command + " " + command)
                    for command in self.docs_command.all_commands
                ]
            )

    def format_options(self, ctx: Context, formatter: DocsCommandHelpTextFormatter):
        DocsBaseCommand.format_description(formatter)
        self.format_sub_commands(formatter)


class DocsSubcommand(click.MultiCommand):
    def __init__(self, command: Optional[List[str]] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.docs_command = DocsCommand()
        self.command = command or self.docs_command.sub_commands
        self.command_string = self.docs_command.sub_command_string
        self.command_callback = self.docs_command.command_callback

    def get_command(self, ctx: Context, cmd_name: str) -> Command:
        """
        Overriding the get_command method from the parent class.

        This method recursively gets creates sub-commands until
        it reaches the leaf command, then it returns that as a click command.

        Parameters
        ----------
        ctx
        cmd_name

        Returns
        -------

        """
        next_command = self.command.pop(0)
        if not self.command:
            return DocsBaseCommand(
                name=next_command,
                short_help=f"Documentation for {self.command_string}",
                callback=self.command_callback,
            )
        return DocsSubcommand(command=self.command)

    def list_commands(self, ctx: Context):
        return self.docs_command.all_commands


class DocsCommand:
    @property
    def command_callback(self):
        impl = CommandImplementation(command=self.sub_command_string)
        return functools.partial(impl.run_command)

    @property
    def all_commands(self):
        return list(Documentation.load().keys())

    @property
    def sub_command_string(self):
        return " ".join(self.sub_commands)

    @property
    def sub_commands(self):
        return self._filter_arguments(sys.argv[2:])

    @property
    def base_command(self):
        return f"sam {COMMAND_NAME}"

    @staticmethod
    def _filter_arguments(commands):
        return list(filter(lambda arg: not arg.startswith("-"), commands))

    def create_command(self):
        if self.sub_commands:
            return DocsSubcommand
        return DocsBaseCommand


class CommandImplementation:
    def __init__(self, command: str):
        self.command = command

    @common_options
    def run_command(self):
        """
        Run the necessary logic for the `sam docs` command
        """
        # TODO: Make sure the docs page exists in the list of docs pages
        browser = BrowserConfiguration()
        documentation = Documentation(browser=browser, command=self.command)
        try:
            documentation.open_docs()
        except BrowserConfigurationError:
            click.echo(ERROR_MESSAGE.format(URL=documentation.url))
        else:
            click.echo(SUCCESS_MESSAGE)


@click.command(name=COMMAND_NAME, help=HELP_TEXT, cls=DocsCommand().create_command())
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@command_exception_handler
def cli(ctx):
    """
    `sam docs` command entry point
    """
