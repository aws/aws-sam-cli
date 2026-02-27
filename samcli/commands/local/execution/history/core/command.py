"""
History Local Execution Command Class.
"""

from click import Context, style

from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.common.execution.history.options import COMMON_EXECUTION_HISTORY_OPTIONS_INFO
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.local.execution.core.command import LocalExecutionBaseCommand


class LocalExecutionHistoryCommand(LocalExecutionBaseCommand):
    def get_formatting_options(self):
        return COMMON_EXECUTION_HISTORY_OPTIONS_INFO

    def format_examples(self, ctx: Context, formatter: CommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            execution_id = "c63eec67-3415-4eb4-a495-116aa3a86278"

            with formatter.indented_section(name="Get execution history", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} {execution_id}"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

            with formatter.indented_section(name="Get execution history in JSON format", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} {execution_id} --format json"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
