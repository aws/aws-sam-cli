import unittest
from unittest.mock import Mock, patch
from samcli.commands.logs.core.command import LogsCommand
from samcli.commands.logs.command import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestLogsCommand(unittest.TestCase):
    @patch.object(LogsCommand, "get_params")
    def test_get_options_logs_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam logs"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE(sriram-mv): One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--stack-name", ""), name="stack_name"),
            MockParams(rv=("--tail", ""), name="tail"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
        ]

        cmd = LogsCommand(name="logs", requires_credentials=True, description=DESCRIPTION)
        expected_output = {
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Additional Options": [("", ""), ("--tail", ""), ("", "")],
            "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [],
            "Fetch from Cloudwatch log groups": [
                ("", ""),
                (
                    "$ sam logs --cw-log-group "
                    "/aws/lambda/myfunction-123 "
                    "--cw-log-group "
                    "/aws/lambda/myfunction-456\x1b[0m",
                    "",
                ),
            ],
            "Fetch logs from resource defined in nested Cloudformation stack": [
                ("", ""),
                ("$ sam " "logs " "---stack-name " "mystack " "-n " "MyNestedStack/HelloWorldFunction\x1b[0m", ""),
            ],
            "Fetch logs from supported resources in Cloudformation stack": [
                ("", ""),
                ("$ sam logs " "---stack-name " "mystack\x1b[0m", ""),
            ],
            "Fetch logs with Lambda Function Logical ID and Cloudformation Stack Name": [
                ("", ""),
                ("$ " "sam " "logs " "-n " "HelloWorldFunction " "--stack-name " "mystack\x1b[0m", ""),
            ],
            "Log Identifier Options": [("", ""), ("--stack-name", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
            "Tail new logs": [("", ""), ("$ sam logs -n HelloWorldFunction --stack-name mystack " "--tail\x1b[0m", "")],
            "View logs for specific time range": [
                ("", ""),
                ("$ sam logs -n HelloWorldFunction " "--stack-name mystack -s '10min ago' " "-e '2min ago'\x1b[0m", ""),
            ],
        }
        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
