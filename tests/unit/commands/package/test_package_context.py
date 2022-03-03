"""Test sam package command"""
from unittest import TestCase
from unittest.mock import patch, MagicMock, Mock, call, ANY
import tempfile


from samcli.commands.package.package_context import PackageContext
from samcli.commands.package.exceptions import PackageFailedError
from samcli.lib.package.artifact_exporter import Template
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.samlib.resource_metadata_normalizer import ResourceMetadataNormalizer


class TestPackageCommand(TestCase):
    def setUp(self):
        self.package_command_context = PackageContext(
            template_file="template-file",
            s3_bucket="s3-bucket",
            s3_prefix="s3-prefix",
            image_repository="image-repo",
            image_repositories=None,
            kms_key_id="kms-key-id",
            output_template_file=None,
            use_json=True,
            force_upload=True,
            no_progressbar=False,
            metadata={},
            region=None,
            profile=None,
        )

    @patch.object(SamLocalStackProvider, "get_stacks")
    @patch.object(Template, "export", MagicMock(sideeffect=OSError))
    @patch("boto3.Session")
    def test_template_permissions_error(self, patched_boto, patched_get_stacks):
        patched_get_stacks.return_value = Mock(), Mock()
        with self.assertRaises(PackageFailedError):
            self.package_command_context.run()

    @patch.object(ResourceMetadataNormalizer, "normalize", MagicMock())
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
                    image_repositories=None,
                    kms_key_id="kms-key-id",
                    output_template_file=temp_output_template_file.name,
                    use_json=True,
                    force_upload=True,
                    no_progressbar=False,
                    metadata={},
                    region="us-east-2",
                    profile=None,
                )
                package_command_context.run()

    @patch.object(ResourceMetadataNormalizer, "normalize", MagicMock())
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.Session")
    def test_template_path_valid(self, patched_boto):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            package_command_context = PackageContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository="image-repo",
                image_repositories=None,
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

    @patch.object(ResourceMetadataNormalizer, "normalize", MagicMock())
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.Session")
    def test_template_path_valid_no_json(self, patched_boto):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            package_command_context = PackageContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository="image-repo",
                image_repositories=None,
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

    @patch("samcli.commands.package.package_context.get_resource_full_path_by_id")
    @patch.object(SamLocalStackProvider, "get_stacks")
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.Session")
    @patch("boto3.client")
    @patch("samcli.commands.package.package_context.get_boto_config_with_user_agent")
    def test_boto_clients_created_with_config(
        self,
        patched_get_config,
        patched_boto_client,
        patched_boto_session,
        patched_get_stacks,
        patched_get_resource_full_path_by_id,
    ):
        patched_get_stacks.return_value = Mock(), Mock()
        patched_get_resource_full_path_by_id.return_value = None
        with self.assertRaises(PackageFailedError):
            package_command_context = PackageContext(
                template_file="template_file",
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository=None,
                image_repositories={"RandomFunction": "ImageRepoUri"},
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

        patched_boto_client.assert_has_calls([call("s3", config=ANY)])
        patched_boto_client.assert_has_calls([call("ecr", config=ANY)])
        patched_boto_client.assert_has_calls([call("signer", config=ANY)])

        patched_get_config.assert_has_calls(
            [call(region_name=ANY, signature_version=ANY), call(region_name=ANY), call(region_name=ANY)]
        )

        print("hello")
