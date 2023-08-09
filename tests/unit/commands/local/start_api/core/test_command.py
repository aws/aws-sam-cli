import unittest
from unittest.mock import Mock, patch
from samcli.commands.local.start_api.cli import InvokeAPICommand
from samcli.commands.local.start_api.cli import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestLocalStartAPICommand(unittest.TestCase):
    @patch.object(InvokeAPICommand, "get_params")
    def test_get_options_local_start_api_command(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam local start-api"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE(sriram-mv): One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--template-file", ""), name="template_file"),
            MockParams(rv=("--parameter-overrides", ""), name="parameter_overrides"),
            MockParams(rv=("--host", ""), name="host"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--hook_name", ""), name="hook_name"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
            MockParams(rv=("--log-file", ""), name="log_file"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--terraform-plan-file", ""), name="terraform_plan_file"),
        ]

        cmd = InvokeAPICommand(name="local start-api", requires_credentials=False, description=DESCRIPTION)
        expected_output = {
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Artifact Location Options": [("", ""), ("--log-file", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Container Options": [("", ""), ("--host", ""), ("", "")],
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [("", ""), ("$sam local start-api\x1b[0m", "")],
            "Extension Options": [("", ""), ("--hook_name", ""), ("", "")],
            "Terraform Hook Options": [("", ""), ("--terraform-plan-file", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
            "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
            "Required Options": [("", ""), ("--template-file", ""), ("", "")],
            "Template Options": [("", ""), ("--parameter-overrides", ""), ("", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
