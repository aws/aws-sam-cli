"""
CLI command for "docs" command
"""
import functools
import sys
from typing import List

import click

from samcli.cli.main import common_options, pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
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


class DocsSubcommand(click.MultiCommand):
    def __init__(self, commands: list, full_command, command_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not commands:
            raise ValueError("Events library is necessary to run this command")
        self.commands = commands
        self.full_command = full_command
        self.command_callback = command_callback

    def get_command(self, ctx, cmd_name):
        next_command = self.commands.pop(0)
        if not len(self.commands):
            return click.Command(
                name=next_command,
                short_help=f"Documentation for {self.full_command}",
                callback=self.command_callback,
            )
        return DocsSubcommand(
            commands=self.commands, full_command=self.full_command, command_callback=self.command_callback
        )

    def list_commands(self, ctx):
        return Documentation.load().keys()


class DocsCommand(DocsSubcommand):
    def __init__(self, *args, **kwargs):
        impl = CommandImplementation(command=self.fully_resolved_command)
        if self.fully_resolved_command not in Documentation.load().keys():
            raise ValueError("Invalid command")
        command_callback = functools.partial(impl.run_command)
        super().__init__(
            commands=self.command_hierarchy,
            full_command=self.fully_resolved_command,
            command_callback=command_callback,
            *args,
            **kwargs,
        )

    @property
    def fully_resolved_command(self):
        return " ".join(self.command_hierarchy)

    @property
    def command_hierarchy(self):
        return self._get_command_hierarchy()

    def _get_command_hierarchy(self) -> List[str]:
        return self._filter_flags(sys.argv[2:])

    @staticmethod
    def _filter_flags(commands):
        return list(filter(lambda arg: not arg.startswith("--"), commands))


class CommandImplementation:
    def __init__(self, command):
        self.command = command

    def run_command(self):
        browser = BrowserConfiguration()
        documentation = Documentation(browser=browser, command=self.command)
        try:
            documentation.open_docs()
        except BrowserConfigurationError:
            click.echo(ERROR_MESSAGE.format(URL=documentation.url))
        else:
            click.echo(SUCCESS_MESSAGE)


@click.command(name="docs", help=HELP_TEXT, cls=DocsCommand)
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
