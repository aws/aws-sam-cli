"""Test sam package command"""
from unittest import TestCase
from mock import patch, MagicMock
import tempfile


from samcli.commands.package.package_context import PackageCommandContext
from samcli.commands.package.artifact_exporter import Template
from samcli.commands.package import exceptions


class TestPackageCommand(TestCase):
    def setUp(self):
        self.package_command_context = PackageCommandContext(
            template_file="template-file",
            s3_bucket="s3-bucket",
            s3_prefix="s3-prefix",
            kms_key_id="kms-key-id",
            output_template_file="output-template-file",
            use_json=True,
            force_upload=True,
            metadata={},
            region=None,
            profile=None,
        )

    @patch("boto3.Session")
    def test_template_path_invalid(self, patched_boto):
        with self.assertRaises(exceptions.InvalidTemplatePathError):
            self.package_command_context.run()

    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.Session")
    def test_template_path_valid_with_output_template(self, patched_boto):
        with tempfile.NamedTemporaryFile(mode="w") as temp_template_file:
            with tempfile.NamedTemporaryFile(mode="w") as temp_output_template_file:
                package_command_context = PackageCommandContext(
                    template_file=temp_template_file.name,
                    s3_bucket="s3-bucket",
                    s3_prefix="s3-prefix",
                    kms_key_id="kms-key-id",
                    output_template_file=temp_output_template_file.name,
                    use_json=True,
                    force_upload=True,
                    metadata={},
                    region=None,
                    profile=None,
                )
                package_command_context.run()

    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.Session")
    def test_template_path_valid(self, patched_boto):
        with tempfile.NamedTemporaryFile(mode="w") as temp_template_file:
            package_command_context = PackageCommandContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                kms_key_id="kms-key-id",
                output_template_file="output-template-file",
                use_json=True,
                force_upload=True,
                metadata={},
                region=None,
                profile=None,
            )
            package_command_context.run()

    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.Session")
    def test_template_path_valid_no_json(self, patched_boto):
        with tempfile.NamedTemporaryFile(mode="w") as temp_template_file:
            package_command_context = PackageCommandContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                kms_key_id="kms-key-id",
                output_template_file="output-template-file",
                use_json=False,
                force_upload=True,
                metadata={},
                region=None,
                profile=None,
            )
            package_command_context.run()
