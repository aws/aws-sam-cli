"""
Base command class for local callback commands
"""

from abc import abstractmethod

from click import Context

from samcli.cli.core.command import CoreCommand
from samcli.cli.core.options import ALL_COMMON_OPTIONS
from samcli.commands.common.formatters import CommandHelpTextFormatter


class LocalCallbackFormatterClass(CommandHelpTextFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(ALL_COMMON_OPTIONS, *args, **kwargs)


class LocalCallbackCommand(CoreCommand):
    """
    Base command class for local callback commands.
    """

    class CustomFormatterContext(Context):
        formatter_class = LocalCallbackFormatterClass

    context_class = CustomFormatterContext

    @abstractmethod
    def format_examples(self, ctx: Context, formatter: CommandHelpTextFormatter):
        """Override this method in subclasses to provide command-specific examples."""
        pass
