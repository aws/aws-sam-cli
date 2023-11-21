import unittest
from unittest.mock import Mock, patch
from samcli.commands.remote.invoke.cli import RemoteInvokeCommand
from samcli.commands.remote.invoke.cli import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestRemoteInvokeCommand(unittest.TestCase):
    @patch.object(RemoteInvokeCommand, "get_params")
    def test_get_options_remote_invoke_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam remote invoke"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE: One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--stack-name", ""), name="stack_name"),
            MockParams(rv=("--parameter", ""), name="parameter"),
            MockParams(rv=("--event", ""), name="event"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        cmd = RemoteInvokeCommand(name="remote invoke", requires_credentials=True, description=DESCRIPTION)
        expected_output = {
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [],
            "Lambda Functions": [],
            "Invoke default lambda function with empty event": [
                ("$sam remote invoke --stack-name hello-world\x1b[0m", ""),
            ],
            "Invoke default lambda function with event passed as text input": [
                ('$sam remote invoke --stack-name hello-world -e \'{"message": "hello!"}\'\x1b[0m', ""),
            ],
            "Invoke named lambda function with an event file": [
                ("$sam remote invoke --stack-name hello-world HelloWorldFunction --event-file event.json\x1b[0m", ""),
            ],
            "Invoke function with event as stdin input": [
                ('$ echo \'{"message": "hello!"}\' | sam remote invoke HelloWorldFunction --event-file -\x1b[0m', ""),
            ],
            "Invoke function using lambda ARN and get the full AWS API response": [
                (
                    "$sam remote invoke arn:aws:lambda:us-west-2:123456789012:function:my-function -e <> --output json\x1b[0m",
                    "",
                ),
            ],
            "Asynchronously invoke function with additional boto parameters": [
                (
                    "$sam remote invoke HelloWorldFunction -e <> --parameter InvocationType=Event --parameter Qualifier=MyQualifier\x1b[0m",
                    "",
                ),
            ],
            "Dry invoke a function to validate parameter values and user/role permissions": [
                (
                    "$sam remote invoke HelloWorldFunction -e <> --output json --parameter InvocationType=DryRun\x1b[0m",
                    "",
                ),
            ],
            "Step Functions": [],
            "Start execution with event passed as text input": [
                (
                    '$sam remote invoke --stack-name mock-stack StockTradingStateMachine -e \'{"message": "hello!"}\'\x1b[0m',
                    "",
                ),
            ],
            "Start execution using its physical-id or ARN with an execution name parameter": [
                (
                    "$sam remote invoke arn:aws:states:us-east-1:123456789012:stateMachine:MySFN -e <> --parameter name=mock-execution-name\x1b[0m",
                    "",
                ),
            ],
            "Start execution with an event file and get the full AWS API response": [
                (
                    "$sam remote invoke --stack-name mock-stack StockTradingStateMachine --event-file event.json --output json\x1b[0m",
                    "",
                ),
            ],
            "Start execution with event as stdin input and pass the X-ray trace header to the execution": [
                (
                    '$ echo \'{"message": "hello!"}\' | $sam remote invoke --stack-name mock-stack StockTradingStateMachine --parameter traceHeader=<>\x1b[0m',
                    "",
                ),
            ],
            "SQS Queue": [],
            "Send a message with the MessageBody passed as event": [
                ("$sam remote invoke --stack-name mock-stack MySQSQueue -e hello-world\x1b[0m", ""),
            ],
            "Send a message using its physical-id and pass event using --event-file": [
                (
                    "$sam remote invoke https://sqs.us-east-1.amazonaws.com/12345678910/QueueName --event-file event.json\x1b[0m",
                    "",
                ),
            ],
            "Send a message using its ARN and delay the specified message": [
                (
                    "$sam remote invoke arn:aws:sqs:region:account_id:queue_name -e hello-world --parameter DelaySeconds=10\x1b[0m",
                    "",
                ),
            ],
            "Send a message along with message attributes and get the full AWS API response": [
                (
                    '$sam remote invoke --stack-name mock-stack MySQSQueue -e hello-world --output json --parameter MessageAttributes=\'{"City": {"DataType": "String", "StringValue": "City"}}\'\x1b[0m',
                    "",
                ),
            ],
            "Send a message to a FIFO SQS Queue": [
                (
                    "$sam remote invoke --stack-name mock-stack MySQSQueue -e hello-world --parameter MessageGroupId=mock-message-group --parameter MessageDeduplicationId=mock-dedup-id\x1b[0m",
                    "",
                ),
            ],
            "Kinesis Data Stream": [],
            "Put a record using the data provided as event": [
                ('$sam remote invoke --stack-name mock-stack MyKinesisStream -e \'{"message": "hello!"}\'\x1b[0m', ""),
            ],
            "Put a record using its physical-id and pass event using --event-file": [
                ("$sam remote invoke MyKinesisStreamName --event-file event.json\x1b[0m", ""),
            ],
            "Put a record using its ARN and override the key hash": [
                (
                    "$sam remote invoke arn:aws:kinesis:us-east-2:123456789012:stream/mystream --event-file event.json --parameter ExplicitHashKey=<>\x1b[0m",
                    "",
                ),
            ],
            "Put a record with a sequence number for ordering with a PartitionKey": [
                (
                    "$sam remote invoke MyKinesisStreamName --event hello-world --parameter SequenceNumberForOrdering=<> --parameter PartitionKey=<>\x1b[0m",
                    "",
                ),
            ],
            "Acronyms": [("ARN", "")],
            "Infrastructure Options": [("", ""), ("--stack-name", ""), ("", "")],
            "Input Event Options": [("", ""), ("--event", ""), ("", "")],
            "Additional Options": [("", ""), ("--parameter", ""), ("", "")],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
