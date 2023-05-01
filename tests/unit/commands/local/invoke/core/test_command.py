import unittest
from unittest.mock import Mock, patch
from samcli.commands.local.invoke.cli import InvokeCommand
from samcli.commands.local.invoke.cli import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestLocalInvokeCommand(unittest.TestCase):
    @patch.object(InvokeCommand, "get_params")
    def test_get_options_local_invoke_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam local invoke"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE(sriram-mv): One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--template-file", ""), name="template_file"),
            MockParams(rv=("--parameter-overrides", ""), name="parameter_overrides"),
            MockParams(rv=("--event", ""), name="event"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--hook_name", ""), name="hook_name"),
            MockParams(rv=("--log-file", ""), name="log_file"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        cmd = InvokeCommand(name="local invoke", requires_credentials=False, description=DESCRIPTION)
        expected_output = {
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Artifact Location Options": [("", ""), ("--log-file", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Container Options": [("", ""), ("--event", ""), ("", "")],
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [],
            "Extension Options": [("", ""), ("--hook_name", ""), ("", "")],
            "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
            "Invoke default lambda function with no event": [("", ""), ("$sam local invoke\x1b[0m", "")],
            "Invoke lambda function with stdin input": [
                ("", ""),
                ('$ echo {"message": "hello!"} | ' "sam local invoke " "HelloWorldFunction -e -\x1b[0m", ""),
            ],
            "Invoke named lambda function with an event file": [
                ("", ""),
                ("$sam local invoke " "HelloWorldFunction -e " "event.json\x1b[0m", ""),
            ],
            "Invoke named lambda function with no event": [
                ("", ""),
                ("$sam local invoke " "HelloWorldFunction\x1b[0m", ""),
            ],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
            "Required Options": [("", ""), ("--template-file", ""), ("", "")],
            "Template Options": [("", ""), ("--parameter-overrides", ""), ("", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
