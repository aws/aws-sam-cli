"""
CLI command for "docs" command
"""
from click import command

from samcli.cli.main import pass_context, print_cmdline_args
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.docs.command_context import COMMAND_NAME, DocsCommandContext
from samcli.commands.docs.core.command import DocsSubcommand, DocsBaseCommand
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version


def create_command():
    if DocsCommandContext().sub_commands:
        return DocsSubcommand
    return DocsBaseCommand


@command(name=COMMAND_NAME, cls=create_command())
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
@command_exception_handler
def cli(ctx):
    """
    `sam docs` command entry point
    """
