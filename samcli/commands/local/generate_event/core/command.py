"""
Generate Event Command Class.
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.local.generate_event.event_generation import GenerateEventCommand


class CoreGenerateEventCommand(CoreCommand, GenerateEventCommand):
    class CustomFormatterContext(Context):
        formatter_class = RootCommandHelpTextFormatter

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: RootCommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Generate event S3 sends to local Lambda function", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} s3 [put/delete]"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Customize event by adding parameter flags.", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} s3 [put/delete] --help"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} s3 [put/delete] --bucket <bucket> --key <key>"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(
                name="Test generated event with serverless function locally!", extra_indents=1
            ):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} s3 [put/delete] --bucket <bucket> --key <key> | "
                                f"{getattr(ctx.parent, 'command_path')} invoke -e -"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

    def format_commands(self, ctx: Context, formatter: RootCommandHelpTextFormatter) -> None:  # type:ignore
        # NOTE(sriram-mv): `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.
        with formatter.indented_section(name="Commands", extra_indents=1):
            formatter.write_rd([RowDefinition(text="\n")])
            formatter.write_rd([RowDefinition(name=command) for command in self.all_cmds.keys()])

    def format_options(self, ctx: Context, formatter: RootCommandHelpTextFormatter) -> None:  # type: ignore
        # NOTE(sriram-mv): `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.
        self.format_description(formatter)
        CoreGenerateEventCommand.format_examples(ctx, formatter)
        self.format_commands(ctx, formatter)
