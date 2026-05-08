"""
Base Command Class for Remote Commands.
"""

from abc import abstractmethod

from click import Context

from samcli.cli.core.command import CoreCommand
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.remote.core.options import ALL_OPTIONS


class RemoteFormatterClass(CommandHelpTextFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(ALL_OPTIONS, *args, **kwargs)


class RemoteCommand(CoreCommand):
    """
    Base command class for remote commands.
    """

    class CustomFormatterContext(Context):
        formatter_class = RemoteFormatterClass

    context_class = CustomFormatterContext

    @abstractmethod
    def format_examples(self, ctx: Context, formatter: CommandHelpTextFormatter):
        """Override this method in subclasses to provide command-specific examples."""
        pass
