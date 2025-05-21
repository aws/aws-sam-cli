"""
Build Command Class.
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.build.core.formatters import BuildCommandHelpTextFormatter
from samcli.commands.build.core.options import OPTIONS_INFO


class BuildCommand(CoreCommand):
    class CustomFormatterContext(Context):
        formatter_class = BuildCommandHelpTextFormatter

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: BuildCommandHelpTextFormatter):
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
                        name=style(f"$ {ctx.command_path} FUNCTION_LOGICAL_ID"),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name=style(f"$ {ctx.command_path} --use-container"),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name=style(f"$ {ctx.command_path} --use-container --container-env-var-file env.json"),
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name=style(f"$ {ctx.command_path} && {ctx.parent.command_path} local invoke"),  # type: ignore
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                    RowDefinition(
                        name=style(f"$ {ctx.command_path} && {ctx.parent.command_path} deploy"),  # type: ignore
                        extra_row_modifiers=[ShowcaseRowModifier()],
                    ),
                ],
            )

    def format_options(self, ctx: Context, formatter: BuildCommandHelpTextFormatter) -> None:  # type:ignore
        # NOTE(sriram-mv): `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        BuildCommand.format_examples(ctx, formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )
