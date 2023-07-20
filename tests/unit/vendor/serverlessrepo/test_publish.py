import json
from unittest import TestCase
from unittest.mock import patch, Mock

from botocore.exceptions import ClientError

from samcli.vendor.serverlessrepo import publish_application
from samcli.vendor.serverlessrepo.exceptions import (
    InvalidApplicationMetadataError,
    S3PermissionsRequired,
    InvalidS3UriError,
    ServerlessRepoClientError,
)
from samcli.vendor.serverlessrepo.parser import get_app_metadata, strip_app_metadata
from samcli.vendor.serverlessrepo.publish import CREATE_APPLICATION, UPDATE_APPLICATION, CREATE_APPLICATION_VERSION

from samcli.yamlhelper import yaml_dump


class TestPublishApplication(TestCase):
    def setUp(self):
        patcher = patch("samcli.vendor.serverlessrepo.publish.boto3")
        self.addCleanup(patcher.stop)
        self.boto3_mock = patcher.start()
        self.serverlessrepo_mock = Mock()
        self.boto3_mock.client.return_value = self.serverlessrepo_mock
        self.template = """
        {
            "Metadata": {
                "AWS::ServerlessRepo::Application": {
                    "Name": "test-app",
                    "Description": "hello world",
                    "Author": "abc",
                    "LicenseUrl": "s3://test-bucket/LICENSE",
                    "ReadmeUrl": "s3://test-bucket/README.md",
                    "Labels": ["test1", "test2"],
                    "HomePageUrl": "https://github.com/abc/def",
                    "SourceCodeUrl": "https://github.com/abc/def",
                    "SemanticVersion": "1.0.0"
                }
            },
            "Resources": { "Key1": {}, "Key2": {} }
        }
        """
        self.template_dict = json.loads(self.template)
        self.yaml_template_without_metadata = yaml_dump(strip_app_metadata(self.template_dict))
        self.application_id = "arn:aws:serverlessrepo:us-east-1:123456789012:applications/test-app"
        self.application_exists_error = ClientError(
            {
                "Error": {
                    "Code": "ConflictException",
                    "Message": "Application with id {} already exists".format(self.application_id),
                }
            },
            "create_application",
        )
        self.not_conflict_exception = ClientError(
            {"Error": {"Code": "BadRequestException", "Message": "Random message"}}, "create_application"
        )
        self.s3_denied_exception = ClientError(
            {
                "Error": {
                    "Code": "BadRequestException",
                    "Message": "Failed to copy S3 object. Access denied: bucket=test-bucket, key=test-file",
                }
            },
            "create_application",
        )
        self.invalid_s3_uri_exception = ClientError(
            {"Error": {"Code": "BadRequestException", "Message": "Invalid S3 URI"}}, "create_application"
        )

    def test_publish_raise_value_error_for_empty_template(self):
        with self.assertRaises(ValueError) as context:
            publish_application("")

        message = str(context.exception)
        expected = "Require SAM template to publish the application"
        self.assertEqual(expected, message)
        self.serverlessrepo_mock.create_application.assert_not_called()

    def test_publish_raise_value_error_for_not_dict_or_string_template(self):
        with self.assertRaises(ValueError) as context:
            publish_application(123)

        message = str(context.exception)
        expected = "Input template should be a string or dictionary"
        self.assertEqual(expected, message)
        self.serverlessrepo_mock.create_application.assert_not_called()

    @patch("samcli.vendor.serverlessrepo.publish.parse_template")
    def test_publish_template_string_should_parse_template(self, parse_template_mock):
        self.serverlessrepo_mock.create_application.return_value = {"ApplicationId": self.application_id}
        parse_template_mock.return_value = self.template_dict
        publish_application(self.template)
        parse_template_mock.assert_called_with(self.template)

    @patch("samcli.vendor.serverlessrepo.publish.copy.deepcopy")
    def test_publish_template_dict_should_copy_template(self, copy_mock):
        self.serverlessrepo_mock.create_application.return_value = {"ApplicationId": self.application_id}
        copy_mock.return_value = self.template_dict
        publish_application(self.template_dict)
        copy_mock.assert_called_with(self.template_dict)

    def test_publish_new_application_should_create_application(self):
        self.serverlessrepo_mock.create_application.return_value = {"ApplicationId": self.application_id}

        actual_result = publish_application(self.template)
        app_metadata_template = get_app_metadata(self.template_dict).template_dict
        expected_result = {
            "application_id": self.application_id,
            "actions": [CREATE_APPLICATION],
            "details": app_metadata_template,
        }
        self.assertEqual(expected_result, actual_result)

        expected_request = dict({"TemplateBody": self.yaml_template_without_metadata}, **app_metadata_template)
        self.serverlessrepo_mock.create_application.assert_called_once_with(**expected_request)
        # publish a new application will only call create_application
        self.serverlessrepo_mock.update_application.assert_not_called()
        self.serverlessrepo_mock.create_application_version.assert_not_called()

    def test_publish_raise_metadata_error_for_invalid_create_application_request(self):
        template_without_app_name = self.template.replace('"Name": "test-app",', "")
        with self.assertRaises(InvalidApplicationMetadataError) as context:
            publish_application(template_without_app_name)

        message = str(context.exception)
        self.assertEqual("Invalid application metadata: 'name properties not provided'", message)
        # create_application shouldn't be called if application metadata is invalid
        self.serverlessrepo_mock.create_application.assert_not_called()

    def test_publish_raise_serverlessrepo_client_error_when_create_application(self):
        self.serverlessrepo_mock.create_application.side_effect = self.not_conflict_exception

        # should raise exception if it's not ConflictException
        with self.assertRaises(ServerlessRepoClientError):
            publish_application(self.template)

        # shouldn't call the following APIs if the exception isn't application already exists
        self.serverlessrepo_mock.update_application.assert_not_called()
        self.serverlessrepo_mock.create_application_version.assert_not_called()

    def test_publish_raise_s3_permission_error_when_create_application(self):
        self.serverlessrepo_mock.create_application.side_effect = self.s3_denied_exception
        with self.assertRaises(S3PermissionsRequired) as context:
            publish_application(self.template)

        message = str(context.exception)
        self.assertIn(
            "The AWS Serverless Application Repository does not have read access to bucket "
            "'test-bucket', key 'test-file'.",
            message,
        )

    def test_publish_raise_invalid_s3_uri_when_create_application(self):
        self.serverlessrepo_mock.create_application.side_effect = self.invalid_s3_uri_exception
        with self.assertRaises(InvalidS3UriError) as context:
            publish_application(self.template)

        message = str(context.exception)
        self.assertIn("Invalid S3 URI", message)

    def test_publish_existing_application_should_update_application_if_version_not_specified(self):
        self.serverlessrepo_mock.create_application.side_effect = self.application_exists_error
        template_without_version = self.template.replace('"SemanticVersion": "1.0.0"', "")

        actual_result = publish_application(template_without_version)
        expected_result = {
            "application_id": self.application_id,
            "actions": [UPDATE_APPLICATION],
            "details": {
                # Name, LicenseUrl and SourceCodeUrl shouldn't show up
                "Description": "hello world",
                "Author": "abc",
                "ReadmeUrl": "s3://test-bucket/README.md",
                "Labels": ["test1", "test2"],
                "HomePageUrl": "https://github.com/abc/def",
            },
        }
        self.assertEqual(expected_result, actual_result)

        self.serverlessrepo_mock.create_application.assert_called_once()
        # should continue to update application if the exception is application already exists
        expected_request = dict({"ApplicationId": self.application_id}, **expected_result["details"])
        self.serverlessrepo_mock.update_application.assert_called_once_with(**expected_request)
        # create_application_version shouldn't be called if version is not provided
        self.serverlessrepo_mock.create_application_version.assert_not_called()

    @patch("samcli.vendor.serverlessrepo.publish._wrap_client_error")
    def test_publish_wrap_client_error_when_update_application(self, wrap_client_error_mock):
        self.serverlessrepo_mock.create_application.side_effect = self.application_exists_error
        self.serverlessrepo_mock.update_application.side_effect = self.not_conflict_exception
        wrap_client_error_mock.return_value = ServerlessRepoClientError(message="client error")
        with self.assertRaises(ServerlessRepoClientError):
            publish_application(self.template)

        # create_application_version shouldn't be called if update_application fails
        self.serverlessrepo_mock.create_application_version.assert_not_called()

    def test_publish_existing_application_should_update_application_if_version_exists(self):
        self.serverlessrepo_mock.create_application.side_effect = self.application_exists_error
        self.serverlessrepo_mock.create_application_version.side_effect = ClientError(
            {"Error": {"Code": "ConflictException", "Message": "Random"}}, "create_application_version"
        )

        actual_result = publish_application(self.template)
        expected_result = {
            "application_id": self.application_id,
            "actions": [UPDATE_APPLICATION],
            "details": {
                # Name, LicenseUrl and SourceCodeUrl shouldn't show up
                "Description": "hello world",
                "Author": "abc",
                "Labels": ["test1", "test2"],
                "HomePageUrl": "https://github.com/abc/def",
                "ReadmeUrl": "s3://test-bucket/README.md",
            },
        }
        self.assertEqual(expected_result, actual_result)

        self.serverlessrepo_mock.create_application.assert_called_once()
        self.serverlessrepo_mock.update_application.assert_called_once()
        self.serverlessrepo_mock.create_application_version.assert_called_once()

    def test_publish_new_version_should_create_application_version(self):
        self.serverlessrepo_mock.create_application.side_effect = self.application_exists_error

        actual_result = publish_application(self.template)
        expected_result = {
            "application_id": self.application_id,
            "actions": [UPDATE_APPLICATION, CREATE_APPLICATION_VERSION],
            "details": {
                # Name and LicenseUrl shouldn't show up since they can't be updated
                "Description": "hello world",
                "Author": "abc",
                "ReadmeUrl": "s3://test-bucket/README.md",
                "Labels": ["test1", "test2"],
                "HomePageUrl": "https://github.com/abc/def",
                "SourceCodeUrl": "https://github.com/abc/def",
                "SemanticVersion": "1.0.0",
            },
        }
        self.assertEqual(expected_result, actual_result)

        self.serverlessrepo_mock.create_application.assert_called_once()
        self.serverlessrepo_mock.update_application.assert_called_once()
        # should continue to create application version
        expected_request = {
            "ApplicationId": self.application_id,
            "SourceCodeUrl": "https://github.com/abc/def",
            "SemanticVersion": "1.0.0",
            "TemplateBody": self.yaml_template_without_metadata,
        }
        self.serverlessrepo_mock.create_application_version.assert_called_once_with(**expected_request)

    @patch("samcli.vendor.serverlessrepo.publish._wrap_client_error")
    def test_publish_wrap_client_error_when_create_application_version(self, wrap_client_error_mock):
        self.serverlessrepo_mock.create_application.side_effect = self.application_exists_error
        self.serverlessrepo_mock.create_application_version.side_effect = self.not_conflict_exception
        wrap_client_error_mock.return_value = ServerlessRepoClientError(message="client error")
        with self.assertRaises(ServerlessRepoClientError):
            publish_application(self.template)

    def test_create_application_with_passed_in_sar_client(self):
        sar_client = Mock()
        sar_client.create_application.return_value = {"ApplicationId": self.application_id}
        publish_application(self.template, sar_client)

        sar_client.create_application.assert_called_once()
        sar_client.update_application.assert_not_called()
        sar_client.create_application_version.assert_not_called()

        # the self initiated boto3 client shouldn't be used
        self.serverlessrepo_mock.create_application.assert_not_called()
        self.serverlessrepo_mock.update_application.assert_not_called()
        self.serverlessrepo_mock.create_application_version.assert_not_called()

    def test_update_application_with_passed_in_sar_client(self):
        sar_client = Mock()
        sar_client.create_application.side_effect = self.application_exists_error
        publish_application(self.template, sar_client)

        sar_client.create_application.assert_called_once()
        sar_client.update_application.assert_called_once()
        sar_client.create_application_version.assert_called_once()

        # the self initiated boto3 client shouldn't be used
        self.serverlessrepo_mock.create_application.assert_not_called()
        self.serverlessrepo_mock.update_application.assert_not_called()
        self.serverlessrepo_mock.create_application_version.assert_not_called()

    def test_create_application_with_licensebody(self):
        self.serverlessrepo_mock.create_application.return_value = {"ApplicationId": self.application_id}
        template_with_licensebody = self.template.replace(
            '"LicenseUrl": "s3://test-bucket/LICENSE"', '"LicenseBody": "test test"'
        )
        actual_result = publish_application(template_with_licensebody)
        expected_result = {
            "application_id": self.application_id,
            "actions": [CREATE_APPLICATION],
            "details": {
                "Author": "abc",
                "Description": "hello world",
                "HomePageUrl": "https://github.com/abc/def",
                "Labels": ["test1", "test2"],
                "LicenseBody": "test test",
                "Name": "test-app",
                "ReadmeUrl": "s3://test-bucket/README.md",
                "SemanticVersion": "1.0.0",
                "SourceCodeUrl": "https://github.com/abc/def",
            },
        }
        self.assertEqual(expected_result, actual_result)

    def test_update_application_with_readmebody(self):
        self.serverlessrepo_mock.create_application.side_effect = self.application_exists_error
        template_with_readmebody = self.template.replace('"SemanticVersion": "1.0.0"', "").replace(
            '"ReadmeUrl": "s3://test-bucket/README.md"', '"ReadmeBody": "test test"'
        )
        actual_result = publish_application(template_with_readmebody)
        expected_result = {
            "application_id": self.application_id,
            "actions": [UPDATE_APPLICATION],
            "details": {
                "Description": "hello world",
                "Author": "abc",
                "ReadmeBody": "test test",
                "Labels": ["test1", "test2"],
                "HomePageUrl": "https://github.com/abc/def",
            },
        }
        self.assertEqual(expected_result, actual_result)


class TestUpdateApplicationMetadata(TestCase):
    def setUp(self):
        patcher = patch("samcli.vendor.serverlessrepo.publish.boto3")
        self.addCleanup(patcher.stop)
        self.boto3_mock = patcher.start()
        self.serverlessrepo_mock = Mock()
        self.boto3_mock.client.return_value = self.serverlessrepo_mock
        self.template = """
        {
            "Metadata": {
                "AWS::ServerlessRepo::Application": {
                    "Name": "test-app",
                    "Description": "hello world",
                    "Author": "abc",
                    "SemanticVersion": "1.0.0"
                }
            }
        }
        """
        self.template_dict = json.loads(self.template)
        self.application_id = "arn:aws:serverlessrepo:us-east-1:123456789012:applications/test-app"
