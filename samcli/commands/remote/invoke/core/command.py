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
            with formatter.indented_section(name="Lambda Functions", extra_indents=1):
                with formatter.indented_section(
                    name="Invoke default lambda function with empty event", extra_indents=1
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(f"$ {ctx.command_path} --stack-name hello-world"),
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
                                name=style(
                                    f"$ {ctx.command_path} --stack-name hello-world -e"
                                    f" '{json.dumps({'message':'hello!'})}'"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Invoke named lambda function with an event file", extra_indents=1
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} --stack-name "
                                    f"hello-world HelloWorldFunction --event-file event.json"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(name="Invoke function with event as stdin input", extra_indents=1):
                    formatter.write_rd(
                        [
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
                    name="Invoke function using lambda ARN and get the full AWS API response", extra_indents=1
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} arn:aws:lambda:us-west-2:123456789012:function:my-function"
                                    f" -e <> --output json"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Asynchronously invoke function with additional boto parameters", extra_indents=1
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} HelloWorldFunction -e <> "
                                    f"--parameter InvocationType=Event --parameter Qualifier=MyQualifier"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Dry invoke a function to validate parameter values and user/role permissions",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} HelloWorldFunction -e <> --output json "
                                    f"--parameter InvocationType=DryRun"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
            with formatter.indented_section(name="Step Functions", extra_indents=1):
                with formatter.indented_section(
                    name="Start execution with event passed as text input",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} --stack-name mock-stack StockTradingStateMachine"
                                    f" -e '{json.dumps({'message':'hello!'})}'"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Start execution using its physical-id or ARN with an execution name parameter",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} arn:aws:states:us-east-1:123456789012:stateMachine:MySFN"
                                    f" -e <> --parameter name=mock-execution-name"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Start execution with an event file and get the full AWS API response",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} --stack-name mock-stack StockTradingStateMachine"
                                    f" --event-file event.json --output json"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Start execution with event as stdin input and pass the X-ray trace header to the execution",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ echo '{json.dumps({'message':'hello!'})}' | "
                                    f"{ctx.command_path} --stack-name mock-stack StockTradingStateMachine"
                                    f" --parameter traceHeader=<>"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
            with formatter.indented_section(name="SQS Queue", extra_indents=1):
                with formatter.indented_section(
                    name="Send a message with the MessageBody passed as event",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(f"$ {ctx.command_path} --stack-name mock-stack MySQSQueue -e hello-world"),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Send a message using its physical-id and pass event using --event-file",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} https://sqs.us-east-1.amazonaws.com/12345678910/QueueName"
                                    f" --event-file event.json"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Send a message using its ARN and delay the specified message",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} arn:aws:sqs:region:account_id:queue_name -e hello-world"
                                    f" --parameter DelaySeconds=10"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Send a message along with message attributes and get the full AWS API response",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} --stack-name mock-stack MySQSQueue -e hello-world"
                                    f" --output json --parameter MessageAttributes="
                                    f"'{json.dumps({'City': {'DataType': 'String', 'StringValue': 'City'}})}'"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )

                with formatter.indented_section(
                    name="Send a message to a FIFO SQS Queue",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} --stack-name mock-stack MySQSQueue -e hello-world"
                                    f" --parameter MessageGroupId=mock-message-group"
                                    f" --parameter MessageDeduplicationId=mock-dedup-id"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
            with formatter.indented_section(name="Kinesis Data Stream", extra_indents=1):
                with formatter.indented_section(
                    name="Put a record using the data provided as event",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} --stack-name mock-stack MyKinesisStream -e"
                                    f" '{json.dumps({'message':'hello!'})}'"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Put a record using its physical-id and pass event using --event-file",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(f"$ {ctx.command_path} MyKinesisStreamName" f" --event-file event.json"),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Put a record using its ARN and override the key hash",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path}"
                                    f" arn:aws:kinesis:us-east-2:123456789012:stream/mystream"
                                    f" --event-file event.json --parameter ExplicitHashKey=<>"
                                ),
                                extra_row_modifiers=[ShowcaseRowModifier()],
                            ),
                        ]
                    )
                with formatter.indented_section(
                    name="Put a record with a sequence number for ordering with a PartitionKey",
                    extra_indents=1,
                ):
                    formatter.write_rd(
                        [
                            RowDefinition(
                                name=style(
                                    f"$ {ctx.command_path} MyKinesisStreamName"
                                    f" --event hello-world --parameter SequenceNumberForOrdering=<>"
                                    f" --parameter PartitionKey=<>"
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
