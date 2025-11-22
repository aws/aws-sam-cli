"""
Invoke Command Class.
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.local.start_api.core.formatters import InvokeStartAPICommandHelpTextFormatter
from samcli.commands.local.start_api.core.options import OPTIONS_INFO


class InvokeAPICommand(CoreCommand):
    class CustomFormatterContext(Context):
        formatter_class = InvokeStartAPICommandHelpTextFormatter

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: InvokeStartAPICommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Setup", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name="Start the local lambda with Amazon API Gateway endpoint",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path}"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Invoke local Lambda endpoint", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name="Invoke Lambda function locally using curl",
                        ),
                        RowDefinition(
                            name=style("$ curl http://127.0.0.1:3000/hello"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

    def format_options(self, ctx: Context, formatter: InvokeStartAPICommandHelpTextFormatter) -> None:  # type:ignore
        # NOTE(sriram-mv): `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        InvokeAPICommand.format_examples(ctx, formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )
