"""
Base Command Class for Local Execution Commands.
"""

from abc import abstractmethod

from click import Context

from samcli.cli.core.command import CoreCommand
from samcli.cli.core.options import ALL_COMMON_OPTIONS
from samcli.commands.common.formatters import CommandHelpTextFormatter


class LocalExecutionFormatterClass(CommandHelpTextFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(ALL_COMMON_OPTIONS, *args, **kwargs)


class LocalExecutionBaseCommand(CoreCommand):
    class CustomFormatterContext(Context):
        formatter_class = LocalExecutionFormatterClass

    context_class = CustomFormatterContext

    @abstractmethod
    def get_formatting_options(self):
        """Override this method in subclasses to provide command-specific formatting options."""
        pass

    @abstractmethod
    def format_examples(self, ctx: Context, formatter: CommandHelpTextFormatter):
        """Override this method in subclasses to provide command-specific examples."""
        pass

    def format_options(
        self, ctx: Context, formatter: CommandHelpTextFormatter  # type:ignore
    ) -> None:
        self.format_description(formatter)
        self.format_examples(ctx, formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=self.get_formatting_options()
        )
