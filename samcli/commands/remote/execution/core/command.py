"""
Base Command Class for Remote Execution Commands.
"""

from click import Context

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.remote.core.command import RemoteCommand
from samcli.commands.remote.core.options import OPTIONS_INFO


class RemoteExecutionBaseCommand(RemoteCommand):
    @staticmethod
    def format_acronyms(formatter: CommandHelpTextFormatter):
        with formatter.indented_section(name="Acronyms", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        name="ARN",
                        text="Amazon Resource Name",
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                ]
            )

    @staticmethod
    def format_execution_arn_note(formatter: CommandHelpTextFormatter):
        """
        Customers may have $LATEST in their execution ARN which doesnt get escaped nicely
        in a shell environment. So, this is a warning for them to prevent confusion.
        """
        with formatter.indented_section(name="Note", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        text="",
                        name="\n  You must ensure that control characters in the execution ARN such as $ are "
                        "escaped properly when using shell commands.",
                    ),
                ]
            )

    def format_options(
        self, ctx: Context, formatter: CommandHelpTextFormatter  # type:ignore
    ) -> None:
        self.format_description(formatter)
        self.format_examples(ctx, formatter)
        self.format_execution_arn_note(formatter)
        self.format_acronyms(formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )
