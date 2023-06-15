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
            "Invoke default lambda function with empty event": [
                ("", ""),
                ("$sam remote invoke --stack-name hello-world\x1b[0m", ""),
            ],
            "Invoke default lambda function with event passed as text input": [
                ("", ""),
                ('$sam remote invoke --stack-name hello-world -e \'{"message": "hello!"}\'\x1b[0m', ""),
            ],
            "Invoke named lambda function with an event file": [
                ("", ""),
                ("$sam remote invoke --stack-name hello-world HelloWorldFunction --event-file event.json\x1b[0m", ""),
            ],
            "Invoke lambda function with event as stdin input": [
                ("", ""),
                ('$ echo \'{"message": "hello!"}\' | sam remote invoke HelloWorldFunction --event-file -\x1b[0m', ""),
            ],
            "Invoke lambda function using lambda ARN and get the full AWS API response": [
                ("", ""),
                (
                    "$sam remote invoke arn:aws:lambda:us-west-2:123456789012:function:my-function -e <> --output json\x1b[0m",
                    "",
                ),
            ],
            "Asynchronously invoke lambda function with additional boto parameters": [
                ("", ""),
                (
                    "$sam remote invoke HelloWorldFunction -e <> --parameter InvocationType=Event --parameter Qualifier=MyQualifier\x1b[0m",
                    "",
                ),
            ],
            "Dry invoke a lambda function to validate parameter values and user/role permissions": [
                ("", ""),
                (
                    "$sam remote invoke HelloWorldFunction -e <> --output json --parameter InvocationType=DryRun\x1b[0m",
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
