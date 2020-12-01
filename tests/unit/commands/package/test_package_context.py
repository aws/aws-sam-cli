"""Test sam package command"""
from unittest import TestCase
from unittest.mock import patch, MagicMock
import tempfile


from samcli.commands.package.package_context import PackageContext
from samcli.commands.package.exceptions import PackageFailedError
from samcli.lib.package.artifact_exporter import Template


class TestPackageCommand(TestCase):
    def setUp(self):
        self.package_command_context = PackageContext(
            template_file="template-file",
            s3_bucket="s3-bucket",
            s3_prefix="s3-prefix",
            image_repository="image-repo",
            kms_key_id="kms-key-id",
            output_template_file=None,
            use_json=True,
            force_upload=True,
            no_progressbar=False,
            metadata={},
            region=None,
            profile=None,
        )

    @patch.object(Template, "export", MagicMock(sideeffect=OSError))
    @patch("boto3.Session")
    def test_template_permissions_error(self, patched_boto):
        with self.assertRaises(PackageFailedError):
            self.package_command_context.run()

    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.Session")
    def test_template_path_valid_with_output_template(self, patched_boto):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_output_template_file:
                package_command_context = PackageContext(
                    template_file=temp_template_file.name,
                    s3_bucket="s3-bucket",
                    s3_prefix="s3-prefix",
                    image_repository="image-repo",
                    kms_key_id="kms-key-id",
                    output_template_file=temp_output_template_file.name,
                    use_json=True,
                    force_upload=True,
                    no_progressbar=False,
                    metadata={},
                    region=None,
                    profile=None,
                )
                package_command_context.run()

    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.Session")
    def test_template_path_valid(self, patched_boto):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            package_command_context = PackageContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository="image-repo",
                kms_key_id="kms-key-id",
                output_template_file=None,
                use_json=True,
                force_upload=True,
                no_progressbar=False,
                metadata={},
                region=None,
                profile=None,
            )
            package_command_context.run()

    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.Session")
    def test_template_path_valid_no_json(self, patched_boto):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            package_command_context = PackageContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository="image-repo",
                kms_key_id="kms-key-id",
                output_template_file=None,
                use_json=False,
                force_upload=True,
                no_progressbar=False,
                metadata={},
                region=None,
                profile=None,
            )
            package_command_context.run()
