import unittest
from unittest.mock import Mock, patch
from samcli.commands.pipeline.bootstrap.core.command import PipelineBootstrapCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestPipelineBootstrapCommand(unittest.TestCase):
    @patch.object(PipelineBootstrapCommand, "get_params")
    def test_get_options_pipeline_bootstrap_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam pipeline bootstrap"
        formatter = MockFormatter(scrub_text=True)
        mock_get_params.return_value = [
            MockParams(rv=("--interactive", ""), name="interactive"),
            MockParams(rv=("--stage", ""), name="stage"),
            MockParams(rv=("--region", ""), name="region"),
            MockParams(rv=("--profile", ""), name="profile"),
            MockParams(rv=("--config-env", ""), name="config_env"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--save-params", ""), name="save_params"),
        ]

        cmd = PipelineBootstrapCommand(name="bootstrap", requires_credentials=True, description="")
        expected_output = {
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Bootstrap Options": [("", ""), ("--interactive", ""), ("", ""), ("--stage", "")],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", ""), ("--profile", "")],
            "Configuration Options": [
                ("", ""),
                ("Learn more about configuration files at:", ""),
                (
                    "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/"
                    "serverless-sam-cli-config.html. ",
                    "",
                ),
                ("", ""),
                ("--config-env", ""),
                ("", ""),
                ("--config-file", ""),
                ("", ""),
                ("--save-params", ""),
            ],
            "Beta Options": [("", ""), ("--beta-features", "")],
            "Other Options": [("", ""), ("--debug", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
