"""
Invoke Command Class.
"""
import json

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.remote.invoke.core.formatters import RemoteInvokeCommandHelpTextFormatter
from samcli.commands.remote.invoke.core.options import OPTIONS_INFO


class RemoteInvokeCommand(CoreCommand):
    class CustomFormatterContext(Context):
        formatter_class = RemoteInvokeCommandHelpTextFormatter

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: RemoteInvokeCommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Invoke default lambda function with empty event", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"${ctx.command_path} --stack-name hello-world"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(
                name="Invoke default lambda function with event passed as text input", extra_indents=1
            ):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"${ctx.command_path} --stack-name hello-world -e '{json.dumps({'message':'hello!'})}'"
                            ),
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
                            name=style(
                                f"${ctx.command_path} --stack-name "
                                f"hello-world HelloWorldFunction --event-file event.json"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Invoke lambda function with event as stdin input", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ echo '{json.dumps({'message':'hello!'})}' | "
                                f"{ctx.command_path} HelloWorldFunction --event-file -"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(
                name="Invoke lambda function using lambda ARN and get the full AWS API response", extra_indents=1
            ):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"${ctx.command_path} arn:aws:lambda:us-west-2:123456789012:function:my-function -e <>"
                                f" --output json"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(
                name="Asynchronously invoke lambda function with additional boto parameters", extra_indents=1
            ):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"${ctx.command_path} HelloWorldFunction -e <> "
                                f"--parameter InvocationType=Event --parameter Qualifier=MyQualifier"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(
                name="Dry invoke a lambda function to validate parameter values and user/role permissions",
                extra_indents=1,
            ):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"${ctx.command_path} HelloWorldFunction -e <> --output json "
                                f"--parameter InvocationType=DryRun"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

    @staticmethod
    def format_acronyms(formatter: RemoteInvokeCommandHelpTextFormatter):
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

    def format_options(self, ctx: Context, formatter: RemoteInvokeCommandHelpTextFormatter) -> None:  # type:ignore
        # NOTE: `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        RemoteInvokeCommand.format_examples(ctx, formatter)
        RemoteInvokeCommand.format_acronyms(formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )
