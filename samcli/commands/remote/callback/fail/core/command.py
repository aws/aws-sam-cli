"""
Command class for remote callback fail command
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.remote.callback.fail.core.options import OPTIONS_INFO
from samcli.commands.remote.core.command import RemoteCommand


class RemoteCallbackFailCommand(RemoteCommand):
    """
    Command class for remote callback fail command.
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
            with formatter.indented_section(name="Send failure callback with no parameters", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(text="\n"),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} my-callback-id"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

            with formatter.indented_section(name="Send failure callback with error message", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(text="\n"),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} my-callback-id --error-message 'Task failed'"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

            with formatter.indented_section(name="Send failure callback with all parameters", extra_indents=1):
                json_data = '{"code": 500}'
                command_example = (
                    f"$ {ctx.command_path} my-callback-id --error-message 'Task failed' "
                    f"--error-type 'ValidationError' --stack-trace 'at line 42' --error-data '{json_data}'"
                )
                formatter.write_rd(
                    [
                        RowDefinition(text="\n"),
                        RowDefinition(
                            name=style(command_example),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
