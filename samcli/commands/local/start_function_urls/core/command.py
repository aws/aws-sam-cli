"""
Start Function URLs Command Class.
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.local.start_function_urls.core.formatters import InvokeFunctionUrlsCommandHelpTextFormatter
from samcli.commands.local.start_function_urls.core.options import OPTIONS_INFO


class InvokeFunctionUrlsCommand(CoreCommand):
    class CustomFormatterContext(Context):
        formatter_class = InvokeFunctionUrlsCommandHelpTextFormatter

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: InvokeFunctionUrlsCommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            formatter.write_rd(
                [
                    RowDefinition(
                        text="\n",
                    ),
                    RowDefinition(
                        name=style(f"$ {ctx.command_path}"),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        text="\n",
                    ),
                    RowDefinition(
                        name="  Start all functions with Function URLs on auto-assigned ports",
                    ),
                    RowDefinition(
                        text="\n",
                    ),
                    RowDefinition(
                        name=style(f"$ {ctx.command_path} --port-range 4000-4010"),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        text="\n",
                    ),
                    RowDefinition(
                        name="  Start with a specific port range",
                    ),
                    RowDefinition(
                        text="\n",
                    ),
                    RowDefinition(
                        name=style(f"$ {ctx.command_path} --function-name MyFunction --port 3001"),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        text="\n",
                    ),
                    RowDefinition(
                        name="  Start a specific function on a specific port",
                    ),
                    RowDefinition(
                        text="\n",
                    ),
                    RowDefinition(
                        name=style(f"$ {ctx.command_path} --env-vars env.json"),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        text="\n",
                    ),
                    RowDefinition(
                        name="  Start with environment variables",
                    ),
                ]
            )

    def format_options(self, ctx: Context, formatter: InvokeFunctionUrlsCommandHelpTextFormatter) -> None:  # type:ignore
        # NOTE(sriram-mv): `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        InvokeFunctionUrlsCommand.format_examples(ctx, formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )
