import unittest
from unittest.mock import Mock, patch
from samcli.commands.deploy.core.command import DeployCommand
from samcli.commands.deploy.command import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestDeployCommand(unittest.TestCase):
    @patch.object(DeployCommand, "get_params")
    def test_get_options_deploy_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam deploy"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE(sriram-mv): One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--s3-bucket", ""), name="s3_bucket"),
            MockParams(rv=("--signing-profiles", ""), name="signing_profiles"),
            MockParams(rv=("--stack-name", ""), name="stack_name"),
            MockParams(rv=("--no-execute-changeset", ""), name="no_execute_changeset"),
            MockParams(rv=("--guided", ""), name="guided"),
        ]

        cmd = DeployCommand(name="deploy", requires_credentials=False, description=DESCRIPTION)
        expected_output = {
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Additional Options": [("", ""), ("--signing-profiles", ""), ("", "")],
            "Deployment Options": [("", ""), ("--no-execute-changeset", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
            "Required Options": [("", ""), ("--stack-name", ""), ("", "")],
            "Infrastructure Options": [("", ""), ("--s3-bucket", ""), ("", "")],
            "Interactive Options": [("", ""), ("--guided", ""), ("", "")],
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Acronyms": [("", ""), ("IAM", ""), ("ARN", ""), ("S3", ""), ("SNS", ""), ("ECR", ""), ("KMS", "")],
            "Examples": [
                ("", ""),
                ("$ sam deploy --guided\x1b[0m", ""),
                (
                    "$ sam deploy --template-file packaged.yaml --stack-name sam-app --capabilities CAPABILITY_IAM\x1b[0m",
                    "",
                ),
                ("$ sam deploy --parameter-overrides 'ParameterKey=InstanceType,ParameterValue=t1.micro'\x1b[0m", ""),
                ("$ sam deploy --parameter-overrides KeyPairName=MyKey InstanceType=t1.micro\x1b[0m", ""),
            ],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
