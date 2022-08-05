import os
from unittest import TestCase
from unittest.mock import Mock, patch

import botocore.exceptions

from samcli.commands.exceptions import NoResourcesMatchGivenTagException
from samcli.commands.test_runner.init.cli import do_cli


class TestCli(TestCase):

    TEST_TEMPLATE_NAME = "test-template-name"
    TEST_ENV_FILE_NAME = "test-envs"

    def test_no_tags_provided(self):
        try:
            do_cli(
                ctx=None,
                tags=None,
                template_name=self.TEST_TEMPLATE_NAME,
                env_file=self.TEST_ENV_FILE_NAME,
                image_uri="test_image_uri",
                runtime="python3.8",
            )
        finally:
            self.assertTrue(os.path.exists(self.TEST_TEMPLATE_NAME))
            os.remove(self.TEST_TEMPLATE_NAME)

    @patch("samcli.commands.test_runner.init.cli.write_file")
    def test_template_create_failure(self, write_file_patch):
        write_file_patch.side_effect = OSError()
        with self.assertRaises(OSError):
            do_cli(
                ctx=None,
                tags=None,
                template_name=self.TEST_TEMPLATE_NAME,
                env_file=self.TEST_ENV_FILE_NAME,
                image_uri="test_image_uri",
                runtime="python3.8",
            )
        self.assertFalse(os.path.exists(self.TEST_TEMPLATE_NAME))

    @patch("samcli.commands.test_runner.init.cli.write_file")
    @patch("samcli.commands.test_runner.init.cli.query_tagging_api")
    @patch("samcli.commands.test_runner.init.cli.get_boto_client_provider_with_config")
    def test_no_resources_match_tags(self, boto_client_provider_patch, query_tagging_api_patch, write_file_patch):
        mock_ctx = Mock()
        mock_ctx.region = "test-region"
        mock_ctx.profile = "test-profile"
        boto_client_provider_patch.return_value = None
        query_tagging_api_patch.return_value = []
        with self.assertRaises(NoResourcesMatchGivenTagException):
            do_cli(
                ctx=mock_ctx,
                tags={"Key": "Value"},
                template_name=self.TEST_TEMPLATE_NAME,
                env_file=self.TEST_ENV_FILE_NAME,
                image_uri="test_image_uri",
                runtime="python3.8",
            )

        write_file_patch.assert_not_called()

    @patch("samcli.commands.test_runner.init.cli.write_file")
    @patch("samcli.commands.test_runner.init.cli.query_tagging_api")
    @patch("samcli.commands.test_runner.init.cli.get_boto_client_provider_with_config")
    def test_failed_tagging_api_query(self, boto_client_provider_patch, query_tagging_api_patch, write_file_patch):
        mock_ctx = Mock()
        mock_ctx.region = "test-region"
        mock_ctx.profile = "test-profile"
        boto_client_provider_patch.return_value = None
        query_tagging_api_patch.side_effect = botocore.exceptions.ClientError(
            operation_name="query-tagging-api",
            error_response={
                "Error": {"Code": "SomeServiceException", "Message": "Details/context around the exception or error"}
            },
        )
        with self.assertRaises(botocore.exceptions.ClientError):
            do_cli(
                ctx=mock_ctx,
                tags={"Key": "Value"},
                template_name=self.TEST_TEMPLATE_NAME,
                env_file=self.TEST_ENV_FILE_NAME,
                image_uri="test_image_uri",
                runtime="python3.8",
            )

        write_file_patch.assert_not_called()

    @patch("samcli.commands.test_runner.init.cli.query_tagging_api")
    @patch("samcli.commands.test_runner.init.cli.get_boto_client_provider_with_config")
    def test_valid_tagging_api_response(self, boto_client_provider_patch, query_tagging_api_patch):
        mock_ctx = Mock()
        mock_ctx.region = "test-region"
        mock_ctx.profile = "test-profile"
        boto_client_provider_patch.return_value = None
        query_tagging_api_patch.return_value = ["arn:aws:lambda:us-east-1:123456789123:function:valid-lambda-arn"]

        try:
            do_cli(
                ctx=mock_ctx,
                tags={"Key": "Value"},
                template_name=self.TEST_TEMPLATE_NAME,
                env_file=self.TEST_ENV_FILE_NAME,
                image_uri="test_image_uri",
                runtime="python3.8",
            )
        finally:
            self.assertTrue(os.path.exists(self.TEST_TEMPLATE_NAME))
            self.assertTrue(os.path.exists(self.TEST_ENV_FILE_NAME))
            os.remove(self.TEST_TEMPLATE_NAME)
            os.remove(self.TEST_ENV_FILE_NAME)
