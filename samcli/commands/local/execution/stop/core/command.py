"""
Stop Local Execution Command Class.
"""

from click import Context, style

from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.common.execution.stop.options import COMMON_EXECUTION_STOP_OPTIONS_INFO
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.local.execution.core.command import LocalExecutionBaseCommand


class LocalExecutionStopCommand(LocalExecutionBaseCommand):
    def get_formatting_options(self):
        return COMMON_EXECUTION_STOP_OPTIONS_INFO

    def format_examples(self, ctx: Context, formatter: CommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            execution_id = "c63eec67-3415-4eb4-a495-116aa3a86278"

            with formatter.indented_section(name="Stop execution without error details", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} {execution_id}"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

            with formatter.indented_section(name="Stop execution with error message and type", extra_indents=1):
                error_options = '--error-message "Execution cancelled" --error-type "UserCancellation"'
                formatter.write_rd(
                    [
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} {execution_id} {error_options}"),
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
                            name=style(f"$ {ctx.command_path} {execution_id} {full_options}"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
