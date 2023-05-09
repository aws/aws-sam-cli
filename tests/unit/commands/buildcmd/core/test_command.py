import unittest
from unittest.mock import Mock, patch
from samcli.commands.build.core.command import BuildCommand
from samcli.commands.build.command import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestBuildCommand(unittest.TestCase):
    @patch.object(BuildCommand, "get_params")
    def test_get_options_build_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam build"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE(sriram-mv): One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--use-container", ""), name="use_container"),
            MockParams(rv=("--hook-name", ""), name="hook_name"),
            MockParams(rv=("--parallel", ""), name="parallel"),
            MockParams(rv=("--build-dir", ""), name="build_dir"),
            MockParams(rv=("--parameter-overrides", ""), name="parameter_overrides"),
            MockParams(rv=("--beta-features", ""), name="beta_features"),
            MockParams(rv=("--template-file", ""), name="template_file"),
        ]

        cmd = BuildCommand(name="sync", requires_credentials=False, description=DESCRIPTION)
        expected_output = {
            "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
            "Container Options": [("", ""), ("--use-container", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Extension Options": [("", ""), ("--hook-name", ""), ("", "")],
            "Build Strategy Options": [("", ""), ("--parallel", ""), ("", "")],
            "Artifact Location Options": [("", ""), ("--build-dir", ""), ("", "")],
            "Template Options": [("", ""), ("--parameter-overrides", ""), ("", "")],
            "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
            "Required Options": [("", ""), ("--template-file", ""), ("", "")],
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [
                ("", ""),
                ("$sam build\x1b[0m", ""),
                ("$sam build FUNCTION_LOGICAL_ID\x1b[0m", ""),
                ("$sam build --use-container\x1b[0m", ""),
                ("$sam build --use-container --container-env-var-file env.json\x1b[0m", ""),
                ("$sam build && sam local invoke\x1b[0m", ""),
                ("$sam build && sam deploy\x1b[0m", ""),
            ],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
