"""
Invoke Command Class.
"""
import json

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.local.invoke.core.formatters import InvokeCommandHelpTextFormatter
from samcli.commands.local.invoke.core.options import OPTIONS_INFO


class InvokeCommand(CoreCommand):
    class CustomFormatterContext(Context):
        formatter_class = InvokeCommandHelpTextFormatter

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: InvokeCommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Invoke default lambda function with no event", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"${ctx.command_path}"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Invoke named lambda function with no event", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"${ctx.command_path} HelloWorldFunction"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Invoke named lambda function with an event file", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"${ctx.command_path} HelloWorldFunction -e event.json"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Invoke lambda function with stdin input", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ echo {json.dumps({'message':'hello!'})} | "
                                f"{ctx.command_path} HelloWorldFunction -e -"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

    def format_options(self, ctx: Context, formatter: InvokeCommandHelpTextFormatter) -> None:  # type:ignore
        # NOTE(sriram-mv): `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        InvokeCommand.format_examples(ctx, formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )
