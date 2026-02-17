import unittest
from unittest.mock import Mock, patch
from samcli.commands.pipeline.init.core.command import PipelineInitCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestPipelineInitCommand(unittest.TestCase):
    @patch.object(PipelineInitCommand, "get_params")
    def test_get_options_pipeline_init_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam pipeline init"
        formatter = MockFormatter(scrub_text=True)
        mock_get_params.return_value = [
            MockParams(rv=("--config-env", ""), name="config_env"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--bootstrap", ""), name="bootstrap"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--save-params", ""), name="save_params"),
        ]

        cmd = PipelineInitCommand(name="init", requires_credentials=False, description="")
        expected_output = {
            "Pipeline Init Options": [("", ""), ("--bootstrap", "")],
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
