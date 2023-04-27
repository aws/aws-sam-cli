import unittest
from unittest.mock import Mock, patch
from samcli.commands.init.core.command import InitCommand
from samcli.commands.init.command import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestInitCommand(unittest.TestCase):
    @patch.object(InitCommand, "get_params")
    def test_get_options_init_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam init"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE(sriram-mv): One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--name", "Application"), name="name"),
            MockParams(rv=("--no-interactive", ""), name="no_interactive"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--tracing", ""), name="tracing"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        cmd = InitCommand(name="init", requires_credentials=False, description=DESCRIPTION)
        expected_output = {
            "Additional Options": [("", ""), ("--tracing", ""), ("", "")],
            "Application Options": [("", ""), ("--name", ""), ("", "")],
            "Beta Options": [("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Customized Interactive Mode": [
                ("", ""),
                ("$ sam init --name sam-app --runtime " "nodejs18.x --architecture arm64\x1b[0m", ""),
                (
                    "$ sam init --name sam-app --runtime "
                    "nodejs18.x --dependency-manager npm "
                    "--app-template hello-world\x1b[0m",
                    "",
                ),
                ("$ sam init --name sam-app --package-type " "image --architecture arm64\x1b[0m", ""),
            ],
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Direct Initialization": [
                ("", ""),
                ("$ sam init --location " "gh:aws-samples/cookiecutter-aws-sam-python\x1b[0m", ""),
                (
                    "$ sam init --location "
                    "git+ssh://git@github.com/aws-samples/cookiecutter-aws-sam-python.git\x1b[0m",
                    "",
                ),
                ("$ sam init --location " "/path/to/template.zip\x1b[0m", ""),
                ("$ sam init --location " "/path/to/template/directory\x1b[0m", ""),
                ("$ sam init --location " "https://example.com/path/to/template.zip\x1b[0m", ""),
            ],
            "Examples": [],
            "Interactive Mode": [("", ""), ("$ sam init\x1b[0m", "")],
            "Non Interactive Options": [("", ""), ("--no-interactive", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
