"""
CLI command for "docs" command
"""
from typing import Type

from click import Command, command

from samcli.cli.main import pass_context
from samcli.commands._utils.command_exception_handler import command_exception_handler
from samcli.commands.docs.command_context import COMMAND_NAME, DocsCommandContext
from samcli.commands.docs.core.command import DocsBaseCommand, DocsSubCommand


def create_command() -> Type[Command]:
    """
    Factory method for creating a Docs command
    Returns
    -------
    Type[Command]
        Sub-command class if the command line args include
        sub-commands, otherwise returns the base command class
    """
    if DocsCommandContext().sub_commands:
        return DocsSubCommand
    return DocsBaseCommand


@command(name=COMMAND_NAME, cls=create_command())
@pass_context
@command_exception_handler
def cli(ctx):
    """
    `sam docs` command entry point
    """
