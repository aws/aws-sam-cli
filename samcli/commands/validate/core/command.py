"""
Validate Command Class.
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.validate.core.options import ALL_OPTIONS, OPTIONS_INFO


class ValidateCommand(CoreCommand):
    class CustomFormatterContext(Context):
        def make_formatter(self):
            return CommandHelpTextFormatter(
                additive_justification=16,
                options=ALL_OPTIONS,
                width=self.terminal_width,
                max_width=self.max_content_width,
            )

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: CommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Validate and Lint", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} --lint"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

    def format_options(self, ctx: Context, formatter: CommandHelpTextFormatter) -> None:  # type:ignore
        # NOTE(sriram-mv): `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        ValidateCommand.format_examples(ctx, formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )
