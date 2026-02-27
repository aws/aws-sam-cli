"""
Execution Stop Command Class.
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.remote.execution.core.command import RemoteExecutionBaseCommand
from samcli.commands.remote.execution.stop.core.options import OPTIONS_INFO


class RemoteExecutionStopCommand(RemoteExecutionBaseCommand):
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

            with formatter.indented_section(name="Stop execution without error details", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} {arn_example}"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

            with formatter.indented_section(name="Stop execution with error message and type", extra_indents=1):
                error_options = '--error-message "Execution cancelled" --error-type "UserCancellation"'
                formatter.write_rd(
                    [
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} {arn_example} {error_options}"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

            with formatter.indented_section(
                name="Stop execution with full error details and stack trace", extra_indents=1
            ):
                full_options = (
                    '--error-message "Task failed" --error-type "TaskFailure" --error-data \'{"reason":"timeout"}\' '
                    '--stack-trace "at function1()" --stack-trace "at function2()"'
                )
                formatter.write_rd(
                    [
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} {arn_example} {full_options}"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
