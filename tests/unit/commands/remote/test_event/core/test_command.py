import unittest
from unittest.mock import Mock, patch
from samcli.commands.remote.test_event.get.core.command import RemoteTestEventGetCommand
from samcli.commands.remote.test_event.list.core.command import RemoteTestEventListCommand
from samcli.commands.remote.test_event.delete.core.command import RemoteTestEventDeleteCommand
from samcli.commands.remote.test_event.put.core.command import RemoteTestEventPutCommand
from samcli.commands.remote.test_event.get.cli import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestRemoteTestEventGetCommand(unittest.TestCase):
    @patch.object(RemoteTestEventGetCommand, "get_params")
    def test_get_options_remote_invoke_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam remote test-event get"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE: One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--stack-name", ""), name="stack_name"),
            MockParams(rv=("--parameter", ""), name="parameter"),
            MockParams(rv=("--name", ""), name="name"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        cmd = RemoteTestEventGetCommand(
            name="remote test-event get", requires_credentials=True, description=DESCRIPTION
        )
        expected_output = {
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [],
            "Get a test event from default Lambda function": [
                ("", ""),
                ("$ sam remote test-event get --stack-name hello-world --name MyEvent\x1b[0m", ""),
            ],
            "Get a test event for a named Lambda function in the stack": [
                ("", ""),
                ("$ sam remote test-event get --stack-name hello-world HelloWorldFunction --name MyEvent\x1b[0m", ""),
            ],
            "Get a test event for a named Lambda function in the stack and save the result to a file": [
                ("", ""),
                (
                    "$ sam remote test-event get --stack-name hello-world HelloWorldFunction --name MyEvent --output-file my-event.json\x1b[0m",
                    "",
                ),
            ],
            "Get a test event for a function using the Lambda ARN": [
                ("", ""),
                (
                    "$ sam remote test-event get arn:aws:lambda:us-west-2:123456789012:function:my-function --name MyEvent\x1b[0m",
                    "",
                ),
            ],
            "Acronyms": [("ARN", "")],
            "Infrastructure Options": [("", ""), ("--stack-name", ""), ("", "")],
            "Test Event Options": [("", ""), ("--name", ""), ("", "")],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)


class TestRemoteTestEventPutCommand(unittest.TestCase):
    @patch.object(RemoteTestEventPutCommand, "get_params")
    def test_put_options_remote_invoke_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam remote test-event put"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE: One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--stack-name", ""), name="stack_name"),
            MockParams(rv=("--parameter", ""), name="parameter"),
            MockParams(rv=("--name", ""), name="name"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        cmd = RemoteTestEventPutCommand(
            name="remote test-event get", requires_credentials=True, description=DESCRIPTION
        )
        expected_output = {
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [],
            "Put a remote test event for default Lambda function using the contents of a file": [
                ("", ""),
                (
                    "$ sam remote test-event put --stack-name hello-world --name MyEvent --file /path/to/event.json\x1b[0m",
                    "",
                ),
            ],
            "Put a remote test event for a named Lambda function using the contents of a file": [
                ("", ""),
                (
                    "$ sam remote test-event put --stack-name hello-world HelloWorldFunction --name MyEvent --file /path/to/event.json\x1b[0m",
                    "",
                ),
            ],
            "Put a remote test event for a named Lambda function with stdin input": [
                ("", ""),
                (
                    '$ echo \'{"message": "hello!"}\' | sam remote test-event put --stack-name hello-world HelloWorldFunction --name MyEvent --file -\x1b[0m',
                    "",
                ),
            ],
            "Put a test event for a function using the Lambda ARN using the contents of a file": [
                ("", ""),
                (
                    "$ sam remote test-event put arn:aws:lambda:us-west-2:123456789012:function:my-function --name MyEvent --file /path/to/event.json\x1b[0m",
                    "",
                ),
            ],
            "Acronyms": [("ARN", "")],
            "Infrastructure Options": [("", ""), ("--stack-name", ""), ("", "")],
            "Test Event Options": [("", ""), ("--name", ""), ("", "")],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)


class TestRemoteTestEventListCommand(unittest.TestCase):
    @patch.object(RemoteTestEventListCommand, "get_params")
    def test_get_options_remote_invoke_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam remote test-event list"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE: One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--stack-name", ""), name="stack_name"),
            MockParams(rv=("--parameter", ""), name="parameter"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        cmd = RemoteTestEventListCommand(
            name="remote test-event list", requires_credentials=True, description=DESCRIPTION
        )
        expected_output = {
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [],
            "List remote test events for default Lambda function": [
                ("", ""),
                ("$ sam remote test-event list --stack-name hello-world\x1b[0m", ""),
            ],
            "List remote test events for a named Lambda function in the stack": [
                ("", ""),
                ("$ sam remote test-event list --stack-name hello-world HelloWorldFunction\x1b[0m", ""),
            ],
            "List remote test events for a function using Lambda ARN": [
                ("", ""),
                (
                    "$ sam remote test-event list arn:aws:lambda:us-west-2:123456789012:function:my-function\x1b[0m",
                    "",
                ),
            ],
            "Acronyms": [("ARN", "")],
            "Infrastructure Options": [("", ""), ("--stack-name", ""), ("", "")],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)


class TestRemoteTestEventDeleteCommand(unittest.TestCase):
    @patch.object(RemoteTestEventDeleteCommand, "get_params")
    def test_get_options_remote_invoke_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam remote test-event delete"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE: One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--stack-name", ""), name="stack_name"),
            MockParams(rv=("--parameter", ""), name="parameter"),
            MockParams(rv=("--name", ""), name="name"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        cmd = RemoteTestEventDeleteCommand(
            name="remote test-event delete", requires_credentials=True, description=DESCRIPTION
        )
        expected_output = {
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [],
            "Delete a test event from default Lambda function": [
                ("", ""),
                ("$ sam remote test-event delete --stack-name hello-world --name MyEvent\x1b[0m", ""),
            ],
            "Delete a test event for a named Lambda function in the stack": [
                ("", ""),
                (
                    "$ sam remote test-event delete --stack-name hello-world HelloWorldFunction --name MyEvent\x1b[0m",
                    "",
                ),
            ],
            "Delete a test event for a function using the Lambda ARN": [
                ("", ""),
                (
                    "$ sam remote test-event delete arn:aws:lambda:us-west-2:123456789012:function:my-function --name MyEvent\x1b[0m",
                    "",
                ),
            ],
            "Acronyms": [("ARN", "")],
            "Infrastructure Options": [("", ""), ("--stack-name", ""), ("", "")],
            "Test Event Options": [("", ""), ("--name", ""), ("", "")],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
