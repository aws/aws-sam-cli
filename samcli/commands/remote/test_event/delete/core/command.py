"""
Delete Test Event Command Class.
"""
from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.remote.test_event.delete.core.formatters import RemoteTestEventDeleteCommandHelpTextFormatter
from samcli.commands.remote.test_event.delete.core.options import OPTIONS_INFO


class RemoteTestEventDeleteCommand(CoreCommand):
    class CustomFormatterContext(Context):
        formatter_class = RemoteTestEventDeleteCommandHelpTextFormatter

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: RemoteTestEventDeleteCommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Delete a test event from default Lambda function", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} --stack-name hello-world --name MyEvent"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(
                name="Delete a test event for a named Lambda function in the stack", extra_indents=1
            ):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} --stack-name hello-world HelloWorldFunction --name MyEvent"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(
                name="Delete a test event for a function using the Lambda ARN", extra_indents=1
            ):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} arn:aws:lambda:us-west-2:123456789012:function:my-function "
                                "--name MyEvent"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

    @staticmethod
    def format_acronyms(formatter: RemoteTestEventDeleteCommandHelpTextFormatter):
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

    def format_options(self, ctx: Context, formatter: RemoteTestEventDeleteCommandHelpTextFormatter):  # type:ignore
        # NOTE: `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        RemoteTestEventDeleteCommand.format_examples(ctx, formatter)
        RemoteTestEventDeleteCommand.format_acronyms(formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )
