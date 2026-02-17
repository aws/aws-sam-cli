"""Pipeline bootstrap core command"""

from typing import Dict

from click import Context

from samcli.cli.core.command import CoreCommand
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.pipeline.bootstrap.core.options import ALL_OPTIONS, OPTIONS_INFO


class PipelineBootstrapCommand(CoreCommand):
    class CustomFormatterContext(Context):
        def make_formatter(self) -> CommandHelpTextFormatter:
            return CommandHelpTextFormatter(
                additive_justification=1,
                options=ALL_OPTIONS,
                width=self.terminal_width,
                max_width=self.max_content_width,
            )

    context_class = CustomFormatterContext

    @staticmethod
    def _get_options_info() -> Dict:
        return OPTIONS_INFO

    def format_options(self, ctx: Context, formatter: CommandHelpTextFormatter) -> None:  # type: ignore
        self.format_description(formatter)
        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )
