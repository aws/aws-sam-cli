"""
Module contains classes for creating the docs command from click
"""

import os
from typing import List, Optional

from click import Command, Context, MultiCommand, style

from samcli.cli.row_modifiers import RowDefinition
from samcli.commands.docs.command_context import COMMAND_NAME, DocsCommandContext
from samcli.commands.docs.core.formatter import DocsCommandHelpTextFormatter

HELP_TEXT = "NEW! Open the documentation in a browser."
DESCRIPTION = """
  Launch the AWS SAM CLI documentation in a browser! This command will
  show information about setting up credentials, the
  AWS SAM CLI lifecycle and other useful details. 

  The command also be run with sub-commands to open specific pages.
"""


class DocsBaseCommand(Command):
    class CustomFormatterContext(Context):
        formatter_class = DocsCommandHelpTextFormatter

    context_class = CustomFormatterContext

    def __init__(self, *args, **kwargs):
        """
        Constructor for instantiating a base command for the docs command
        """
        self.docs_command = DocsCommandContext()
        command_callback = self.docs_command.command_callback
        super().__init__(name=COMMAND_NAME, help=HELP_TEXT, callback=command_callback)

    @staticmethod
    def format_description(formatter: DocsCommandHelpTextFormatter):
        """
        Formats the description of the help text for the docs command.

        Parameters
        ----------
        formatter: DocsCommandHelpTextFormatter
            A formatter instance to use for formatting the help text
        """
        with formatter.indented_section(name="Description", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        text="",
                        name=DESCRIPTION
                        + style(f"{os.linesep}  This command does not require access to AWS credentials.", bold=True),
                    ),
                ],
            )

    def format_sub_commands(self, formatter: DocsCommandHelpTextFormatter):
        """
        Formats the sub-commands of the help text for the docs command.

        Parameters
        ----------
        formatter: DocsCommandHelpTextFormatter
            A formatter instance to use for formatting the help text
        """
        with formatter.indented_section(name="Commands", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(self.docs_command.base_command + " " + command)
                    for command in self.docs_command.all_commands
                ],
                col_max=50,
            )

    def format_options(self, ctx: Context, formatter: DocsCommandHelpTextFormatter):  # type:ignore
        """
        Overrides the format_options method from the parent class to update
        the help text formatting in a consistent method for the AWS SAM CLI

        Parameters
        ----------
        ctx: Context
            The click command context
        formatter: DocsCommandHelpTextFormatter
            A formatter instance to use for formatting the help text
        """
        DocsBaseCommand.format_description(formatter)
        self.format_sub_commands(formatter)


class DocsSubCommand(MultiCommand):
    def __init__(self, command: Optional[List[str]] = None, *args, **kwargs):
        """
        Constructor for instantiating a sub-command for the docs command

        Parameters
        ----------
        command: Optional[List[str]]
            Optional list of strings representing the fully resolved command name (e.g. ["docs", "local", "invoke"])
        """
        super().__init__(*args, **kwargs)
        self.docs_command = DocsCommandContext()
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
        ctx: Context
            The click command context
        cmd_name: str
            Name of the next command to be added as a sub-command or the leaf command

        Returns
        -------
        Command
            Returns either a sub-command to be recursively added to the command tree,
            or the leaf command to be invoked by the command handler

        """
        next_command = self.command.pop(0)
        if not self.command:
            return DocsBaseCommand(
                name=next_command,
                short_help=f"Documentation for {self.command_string}",
                callback=self.command_callback,
            )
        return DocsSubCommand(command=self.command)

    def list_commands(self, ctx: Context) -> List[str]:
        """
        Overrides the list_command method from the parent class.
        Used for the Command class to understand all possible sub-commands.

        Parameters
        ----------
        ctx: Context
            The click command context

        Returns
        -------
        List[str]
            List of strings representing sub-commands callable by the docs command
        """
        return self.docs_command.all_commands
