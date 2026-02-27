"""
Execution History Command Class.
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.remote.execution.core.command import RemoteExecutionBaseCommand
from samcli.commands.remote.execution.history.core.options import OPTIONS_INFO


class RemoteExecutionHistoryCommand(RemoteExecutionBaseCommand):
    def format_options(
        self, ctx: Context, formatter: CommandHelpTextFormatter  # type:ignore
    ) -> None:
        self.format_description(formatter)
        self.format_examples(ctx, formatter)
        self.format_acronyms(formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )

    def format_examples(self, ctx: Context, formatter: CommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            arn_example = (
                "arn:aws:lambda:us-east-1:123456789012:function:MyFunction:$LATEST/"
                "durable-execution/my-execution-name/my-execution-id"
            )

            with formatter.indented_section(name="Get execution history", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} {arn_example}"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

            with formatter.indented_section(name="Get execution history in JSON format", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} {arn_example} --format json"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
