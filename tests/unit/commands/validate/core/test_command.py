import unittest
from unittest.mock import Mock, patch
from samcli.commands.validate.core.command import ValidateCommand
from samcli.commands.validate.validate import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestValidateCommand(unittest.TestCase):
    @patch.object(ValidateCommand, "get_params")
    def test_get_options_validate_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam validate"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE(sriram-mv): One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--template-file", ""), name="template_file"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--lint", ""), name="lint"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
        ]

        cmd = ValidateCommand(name="validate", requires_credentials=False, description=DESCRIPTION)
        expected_output = {
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
            "Required Options": [("", ""), ("--template-file", ""), ("", "")],
            "Lint Options": [("", ""), ("--lint", ""), ("", "")],
            "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [],
            "Validate and Lint": [("", ""), ("$sam validate --lint\x1b[0m", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
