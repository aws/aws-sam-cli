from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.commands.package.command import do_cli


class TestPackageCliCommand(TestCase):
    def setUp(self):

        self.template_file = "input-template-file"
        self.s3_bucket = "s3-bucket"
        self.s3_prefix = "s3-prefix"
        self.kms_key_id = "kms-key-id"
        self.output_template_file = "output-template-file"
        self.use_json = True
        self.force_upload = False
        self.metadata = {"abc": "def"}
        self.region = None
        self.profile = None

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    def test_all_args(self, package_command_context, click_mock):

        context_mock = Mock()
        package_command_context.return_value.__enter__.return_value = context_mock

        do_cli(
            template_file=self.template_file,
            s3_bucket=self.s3_bucket,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key_id,
            output_template_file=self.output_template_file,
            use_json=self.use_json,
            force_upload=self.force_upload,
            metadata=self.metadata,
            region=self.region,
            profile=self.profile,
        )

        package_command_context.assert_called_with(
            template_file=self.template_file,
            s3_bucket=self.s3_bucket,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key_id,
            output_template_file=self.output_template_file,
            use_json=self.use_json,
            force_upload=self.force_upload,
            metadata=self.metadata,
            region=self.region,
            profile=self.profile,
        )

        context_mock.run.assert_called_with()
        self.assertEqual(context_mock.run.call_count, 1)
