import unittest
from unittest.mock import Mock, patch
from samcli.commands.local.start_lambda.cli import InvokeLambdaCommand
from samcli.commands.local.start_lambda.cli import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestLocalStartLambdaCommand(unittest.TestCase):
    @patch.object(InvokeLambdaCommand, "get_params")
    def test_get_options_local_start_lambda_command(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam local start-lambda"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE(sriram-mv): One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--template-file", ""), name="template_file"),
            MockParams(rv=("--parameter-overrides", ""), name="parameter_overrides"),
            MockParams(rv=("--port", ""), name="port"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--hook_name", ""), name="hook_name"),
            MockParams(rv=("--log-file", ""), name="log_file"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--terraform-plan-file", ""), name="terraform_plan_file"),
        ]

        cmd = InvokeLambdaCommand(name="local start-lambda", requires_credentials=False, description=DESCRIPTION)
        expected_output = {
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [],
            "Setup": [
                ("", ""),
                ("Start the local lambda endpoint for multiple functions", ""),
                ("$ sam local start-lambda HelloWorldFunctionOne HelloWorldFunctionTwo\x1b[0m", ""),
            ],
            "Invoke local Lambda endpoint": [
                ("", ""),
                ("Use AWS SDK in automated tests.", ""),
                (
                    "\n        self.lambda_client = boto3.client('lambda',\n                                          endpoint_url=\"http://127.0.0.1:3001\",\n                                          use_ssl=False,\n                                          verify=False,\n                                          config=Config(signature_version=UNSIGNED,\n                                                        read_timeout=0,\n                                                        retries={'max_attempts': 0}))\n        self.lambda_client.invoke(FunctionName=\"HelloWorldFunction\")\n        ",
                    "",
                ),
            ],
            "Required Options": [("", ""), ("--template-file", ""), ("", "")],
            "Template Options": [("", ""), ("--parameter-overrides", ""), ("", "")],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Container Options": [("", ""), ("--port", ""), ("", "")],
            "Artifact Location Options": [("", ""), ("--log-file", ""), ("", "")],
            "Extension Options": [("", ""), ("--hook_name", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Terraform Hook Options": [("", ""), ("--terraform-plan-file", ""), ("", "")],
            "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
