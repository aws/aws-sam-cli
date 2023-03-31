import unittest
from unittest.mock import Mock, patch
from samcli.commands.sync.core.command import SyncCommand
from samcli.commands.sync.command import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestSyncCommand(unittest.TestCase):
    @patch.object(SyncCommand, "get_params")
    def test_get_options_sync_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam sync"
        formatter = MockFormatter(scrub_text=True)
        # NOTE(sriram-mv): One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--stack-name", ""), name="stack_name"),
            MockParams(rv=("--resource", ""), name="resource"),
            MockParams(rv=("--s3-bucket", ""), name="s3_bucket"),
        ]

        cmd = SyncCommand(name="sync", requires_credentials=True, description=DESCRIPTION)
        expected_output = {
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Acronyms": [("IAM", ""), ("ARN", ""), ("S3", ""), ("SNS", ""), ("ECR", ""), ("KMS", "")],
            "Additional Options": [("", ""), ("--resource", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [
                ("", ""),
                ("$sam sync --watch --stack-name {stack}\x1b[0m", ""),
                ("$sam sync --code --watch --stack-name {stack}\x1b[0m", ""),
                ("$sam sync --code --stack-name {stack} --resource-id " "{ChildStack}/{ResourceId}\x1b[0m", ""),
            ],
            "Infrastructure Options": [("", ""), ("--s3-bucket", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
            "Required Options": [("", ""), ("--stack-name", ""), ("", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
