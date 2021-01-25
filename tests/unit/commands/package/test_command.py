from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.commands.package.command import do_cli


class TestPackageCliCommand(TestCase):
    def setUp(self):

        self.template_file = "input-template-file"
        self.s3_bucket = "s3-bucket"
        self.image_repository = "image-repo"
        self.image_repositories = None
        self.s3_prefix = "s3-prefix"
        self.kms_key_id = "kms-key-id"
        self.output_template_file = "output-template-file"
        self.use_json = True
        self.force_upload = False
        self.no_progressbar = (False,)
        self.metadata = {"abc": "def"}
        self.region = None
        self.profile = None
        self.resolve_s3 = False
        self.signing_profiles = {"MyFunction": {"profile_name": "ProfileName", "profile_owner": "Profile Owner"}}

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    def test_all_args(self, package_command_context, click_mock):

        context_mock = Mock()
        package_command_context.return_value.__enter__.return_value = context_mock

        do_cli(
            template_file=self.template_file,
            s3_bucket=self.s3_bucket,
            s3_prefix=self.s3_prefix,
            image_repository=self.image_repository,
            image_repositories=self.image_repositories,
            kms_key_id=self.kms_key_id,
            output_template_file=self.output_template_file,
            use_json=self.use_json,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
            metadata=self.metadata,
            region=self.region,
            profile=self.profile,
            resolve_s3=self.resolve_s3,
            signing_profiles=self.signing_profiles,
        )

        package_command_context.assert_called_with(
            template_file=self.template_file,
            s3_bucket=self.s3_bucket,
            s3_prefix=self.s3_prefix,
            image_repository=self.image_repository,
            image_repositories=self.image_repositories,
            kms_key_id=self.kms_key_id,
            output_template_file=self.output_template_file,
            use_json=self.use_json,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
            metadata=self.metadata,
            region=self.region,
            profile=self.profile,
            signing_profiles=self.signing_profiles,
        )

        context_mock.run.assert_called_with()
        self.assertEqual(context_mock.run.call_count, 1)

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.package.command.manage_stack")
    def test_all_args_resolve_s3(self, mock_managed_stack, package_command_context, click_mock):
        context_mock = Mock()
        package_command_context.return_value.__enter__.return_value = context_mock
        mock_managed_stack.return_value = "managed-s3-bucket"

        do_cli(
            template_file=self.template_file,
            s3_bucket=None,
            s3_prefix=self.s3_prefix,
            image_repository=self.image_repository,
            image_repositories=self.image_repositories,
            kms_key_id=self.kms_key_id,
            output_template_file=self.output_template_file,
            use_json=self.use_json,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
            metadata=self.metadata,
            region=self.region,
            profile=self.profile,
            resolve_s3=True,
            signing_profiles=self.signing_profiles,
        )

        package_command_context.assert_called_with(
            template_file=self.template_file,
            s3_bucket="managed-s3-bucket",
            s3_prefix=self.s3_prefix,
            image_repository=self.image_repository,
            image_repositories=self.image_repositories,
            kms_key_id=self.kms_key_id,
            output_template_file=self.output_template_file,
            use_json=self.use_json,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
            metadata=self.metadata,
            region=self.region,
            profile=self.profile,
            signing_profiles=self.signing_profiles,
        )

        context_mock.run.assert_called_with()
        self.assertEqual(context_mock.run.call_count, 1)
