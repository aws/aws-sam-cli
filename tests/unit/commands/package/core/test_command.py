import unittest
from unittest.mock import Mock, patch, MagicMock
from samcli.commands.package.core.command import PackageCommand
from samcli.commands.package.command import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestPackageCommand(unittest.TestCase):
    @patch.object(PackageCommand, "get_params")
    def test_get_options_package_command_text(self, mock_get_params):
        with patch("click.get_current_context", return_value=MagicMock()) as mock_get_current_context:
            # Set up the chain of calls to return 'mock' on .get()
            mock_get_current_context.return_value.obj.console.capture().__enter__().get.return_value = "mock"
            ctx = Mock()
            ctx.command_path = "sam package"
            ctx.parent.command_path = "sam"
            formatter = MockFormatter(scrub_text=True)
            # NOTE(sriram-mv): One option per option section.
            mock_get_params.return_value = [
                MockParams(rv=("--region", "Region"), name="region"),
                MockParams(rv=("--debug", ""), name="debug"),
                MockParams(rv=("--config-file", ""), name="config_file"),
                MockParams(rv=("--s3-prefix", ""), name="s3_prefix"),
                MockParams(rv=("--s3-bucket", ""), name="s3_bucket"),
                MockParams(rv=("--signing-profiles", ""), name="signing_profiles"),
                MockParams(rv=("--stack-name", ""), name="stack_name"),
                MockParams(rv=("--force-upload", ""), name="force_upload"),
                MockParams(rv=("--beta-features", ""), name="beta_features"),
            ]

            cmd = PackageCommand(name="package", requires_credentials=False, description=DESCRIPTION)
            expected_output = {
                "AWS Credential Options": [("", ""), ("--region", ""), ("", "")],
                "Acronyms": [("", ""), ("S3", ""), ("ECR", ""), ("KMS", "")],
                "Additional Options": [("", ""), ("--signing-profiles", ""), ("", "")],
                "Automatic resolution of S3 buckets": [("", ""), ("$ sam package --resolve-s3\x1b[0m", "")],
                "Beta Options": [("", ""), ("--beta-features", ""), ("", "")],
                "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
                "Customized location for uploading artifacts": [
                    ("", ""),
                    ("$ sam package --s3-bucket " "S3_BUCKET " "--output-template-file " "packaged.yaml\x1b[0m", ""),
                ],
                "Description": [
                    (
                        "\n"
                        "  Creates and uploads artifacts based on the package type "
                        "of a given resource.\n"
                        "  It uploads local images to ECR for `Image` package "
                        "types.\n"
                        "  It creates a zip of code and dependencies and uploads it "
                        "to S3 for `Zip` package types. \n"
                        "  \n"
                        "  A new template is returned which replaces references to "
                        "local artifacts\n"
                        "  with the AWS location where the command uploaded the "
                        "artifacts.\n"
                        "    \x1b[1m\n"
                        "  This command may not require access to AWS "
                        "credentials.\x1b[0m",
                        "",
                    )
                ],
                "Examples": [],
                "Get packaged template": [
                    ("", ""),
                    ("$ sam package --resolve-s3 --output-template-file " "packaged.yaml\x1b[0m", ""),
                ],
                "Infrastructure Options": [("", ""), ("--s3-prefix", ""), ("", "")],
                "Other Options": [("", ""), ("--debug", ""), ("", "")],
                "Package Management Options": [("", ""), ("--force-upload", ""), ("", "")],
                "Required Options": [("", ""), ("--s3-bucket", ""), ("", "")],
                "Supported Resources": [("\n", ""), ("mock", "")],
            }

            cmd.format_options(ctx, formatter)
            self.assertEqual(formatter.data, expected_output)
