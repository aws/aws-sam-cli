"""
Command class for local callback succeed command
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.local.callback.core.command import LocalCallbackCommand
from samcli.commands.local.callback.succeed.core.options import OPTIONS_INFO


class LocalCallbackSucceedCommand(LocalCallbackCommand):
    """
    Command class for local callback succeed command.
    """

    def format_options(
        self, ctx: Context, formatter: CommandHelpTextFormatter  # type:ignore
    ) -> None:
        self.format_description(formatter)
        self.format_examples(ctx, formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )

    def format_examples(self, ctx: Context, formatter: CommandHelpTextFormatter):
        """Format command examples for help text"""
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Send success callback with no result", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(text="\n"),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} my-callback-id"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

            with formatter.indented_section(name="Send success callback with result", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(text="\n"),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} my-callback-id --result 'Task completed successfully'"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

            with formatter.indented_section(name="Send success callback with short option", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(text="\n"),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} my-callback-id -r 'Success result'"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
