from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.logs.core.formatters import LogsCommandHelpTextFormatter
from samcli.commands.logs.core.options import OPTIONS_INFO

COL_SIZE_MODIFIER = 38


class LogsCommand(CoreCommand):
    class CustomFormatterContext(Context):
        formatter_class = LogsCommandHelpTextFormatter

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: LogsCommandHelpTextFormatter):
        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(
                name="Fetch logs with Lambda Function Logical ID and Cloudformation Stack Name"
            ):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} -n HelloWorldFunction --stack-name mystack"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="View logs for specific time range"):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} -n HelloWorldFunction --stack-name mystack -s "
                                f"'10min ago' -e '2min ago'"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Tail new logs"):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} -n HelloWorldFunction --stack-name " f"mystack --tail"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Fetch from Cloudwatch log groups"):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} --cw-log-group /aws/lambda/myfunction-123 "
                                f"--cw-log-group /aws/lambda/myfunction-456"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

            with formatter.indented_section(name="Fetch logs from supported resources in Cloudformation stack"):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(f"$ {ctx.command_path} ---stack-name mystack"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

            with formatter.indented_section(name="Fetch logs from resource defined in nested Cloudformation stack"):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name=style(
                                f"$ {ctx.command_path} ---stack-name mystack -n MyNestedStack/HelloWorldFunction"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

    def format_options(self, ctx: Context, formatter: LogsCommandHelpTextFormatter) -> None:  # type:ignore
        # `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        LogsCommand.format_examples(ctx, formatter)

        CoreCommand._format_options(
            ctx=ctx,
            params=self.get_params(ctx),
            formatter=formatter,
            formatting_options=OPTIONS_INFO,
            write_rd_overrides={"col_max": COL_SIZE_MODIFIER},
        )
