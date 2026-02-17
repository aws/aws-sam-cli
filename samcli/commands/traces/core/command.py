"""
Traces Command Class
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.traces.core.options import ALL_OPTIONS, OPTIONS_INFO


class TracesCommand(CoreCommand):
    class CustomFormatterContext(Context):
        def make_formatter(self):
            return CommandHelpTextFormatter(
                options=ALL_OPTIONS,
                width=self.terminal_width,
                max_width=self.max_content_width,
            )

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: CommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Fetch traces by ID", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} --trace-id tracing-id-1 --trace-id tracing-id-2"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Tail traces as they become available", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} --tail"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

    def format_options(self, ctx: Context, formatter: CommandHelpTextFormatter):  # type: ignore
        self.format_description(formatter)
        TracesCommand.format_examples(ctx, formatter)
        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )
