"""
Command class for local callback heartbeat command
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.local.callback.core.command import LocalCallbackCommand
from samcli.commands.local.callback.heartbeat.core.options import OPTIONS_INFO


class LocalCallbackHeartbeatCommand(LocalCallbackCommand):
    """
    Command class for local callback heartbeat command.
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
            with formatter.indented_section(name="Send heartbeat callback", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(text="\n"),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} my-callback-id"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
