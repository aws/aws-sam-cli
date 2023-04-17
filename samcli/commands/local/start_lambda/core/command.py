"""
Invoke Command Class.
"""

from click import Context, style

from samcli.cli.core.command import CoreCommand
from samcli.cli.row_modifiers import RowDefinition, ShowcaseRowModifier
from samcli.commands.local.start_lambda.core.formatters import InvokeStartLambdaCommandHelpTextFormatter
from samcli.commands.local.start_lambda.core.options import OPTIONS_INFO


class InvokeLambdaCommand(CoreCommand):
    class CustomFormatterContext(Context):
        formatter_class = InvokeStartLambdaCommandHelpTextFormatter

    context_class = CustomFormatterContext

    @staticmethod
    def format_examples(ctx: Context, formatter: InvokeStartLambdaCommandHelpTextFormatter):
        AWS_SDK_EXAMPLE = """
        self.lambda_client = boto3.client('lambda',
                                          endpoint_url="http://127.0.0.1:3001",
                                          use_ssl=False,
                                          verify=False,
                                          config=Config(signature_version=UNSIGNED,
                                                        read_timeout=0,
                                                        retries={'max_attempts': 0}))
        self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        """

        with formatter.indented_section(name="Examples", extra_indents=1):
            with formatter.indented_section(name="Setup", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name="Start the local lambda endpoint.",
                        ),
                        RowDefinition(
                            name=style(f"${ctx.command_path}"),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Using AWS CLI", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name="Invoke Lambda function locally using the AWS CLI.",
                        ),
                        RowDefinition(
                            name=style(
                                "$ aws lambda invoke --function-name HelloWorldFunction "
                                "--endpoint-url http://127.0.0.1:3001 --no-verify-ssl out.txt"
                            ),
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )
            with formatter.indented_section(name="Using AWS SDK", extra_indents=1):
                formatter.write_rd(
                    [
                        RowDefinition(
                            text="\n",
                        ),
                        RowDefinition(
                            name="Use AWS SDK in automated tests.",
                        ),
                        RowDefinition(
                            name=AWS_SDK_EXAMPLE,
                            extra_row_modifiers=[ShowcaseRowModifier()],
                        ),
                    ]
                )

    def format_options(self, ctx: Context, formatter: InvokeStartLambdaCommandHelpTextFormatter) -> None:  # type:ignore
        # NOTE(sriram-mv): `ignore` is put in place here for mypy even though it is the correct behavior,
        # as the `formatter_class` can be set in subclass of Command. If ignore is not set,
        # mypy raises argument needs to be HelpFormatter as super class defines it.

        self.format_description(formatter)
        InvokeLambdaCommand.format_examples(ctx, formatter)

        CoreCommand._format_options(
            ctx=ctx, params=self.get_params(ctx), formatter=formatter, formatting_options=OPTIONS_INFO
        )
