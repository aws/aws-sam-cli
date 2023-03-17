"""
CLI command for "docs" command
"""
import functools
import sys
from typing import List, Optional

import click
from click import Command, Context

from samcli.cli.main import common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.exceptions import UserException
from samcli.lib.docs.browser_configuration import BrowserConfiguration, BrowserConfigurationError
from samcli.lib.docs.documentation import Documentation
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

HELP_TEXT = """Launch the AWS SAM CLI documentation in a browser! This command will
    show information about setting up credentials, the
    AWS SAM CLI lifecycle and other useful details. 
"""

SUCCESS_MESSAGE = "Documentation page opened in a browser"
ERROR_MESSAGE = "Failed to open a web browser. Use the following link to navigate to the documentation page: {URL}"


class InvalidDocsCommandException(UserException):
    """
    Exception when the docs command fails
    """


class DocsBaseCommand(click.Command):
    def __init__(self, *args, **kwargs):
        command_callback = DocsCommand().command_callback
        super().__init__(name="docs", callback=command_callback)


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
        if not len(self.command):
            return click.Command(
                name=next_command,
                short_help=f"Documentation for {self.command_string}",
                callback=self.command_callback,
            )
        return DocsSubcommand(command=self.command)

    def list_commands(self, ctx: Context):
        return list(Documentation.load().keys())


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


@click.command(name="docs", help=HELP_TEXT, cls=DocsCommand().create_command())
@common_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@command_exception_handler
def cli(ctx):
    """
    `sam docs` command entry point
    """
