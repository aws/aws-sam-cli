"""Test sam publish CLI."""
import json
from unittest import TestCase
from unittest.mock import patch, call, Mock

from serverlessrepo.exceptions import ServerlessRepoError, InvalidS3UriError
from serverlessrepo.publish import CREATE_APPLICATION, UPDATE_APPLICATION
from serverlessrepo.parser import METADATA, SERVERLESS_REPO_APPLICATION
from parameterized import parameterized, param

from samcli.commands.publish.command import do_cli as publish_cli, SEMANTIC_VERSION
from samcli.commands.exceptions import UserException
from samcli.commands._utils.template import TemplateFailedParsingException, TemplateNotFoundException


class TestCli(TestCase):
    def setUp(self):
        self.template = "./template"
        self.application_id = "arn:aws:serverlessrepo:us-east-1:123456789012:applications/hello"
        self.ctx_mock = Mock()
        self.ctx_mock.region = "us-east-1"
        self.console_link = (
            "Click the link below to view your application in AWS console:\n"
            "https://console.aws.amazon.com/serverlessrepo/home?region={}#/published-applications/{}"
        )

    @parameterized.expand([param(TemplateFailedParsingException), param(TemplateNotFoundException)])
    @patch("samcli.commands.publish.command.get_template_data")
    @patch("samcli.commands.publish.command.click")
    def test_must_raise_if_invalid_template(self, exception_to_raise, click_mock, get_template_data_mock):
        get_template_data_mock.side_effect = exception_to_raise("Template not found")
        with self.assertRaises(exception_to_raise) as context:
            publish_cli(self.ctx_mock, self.template, None)

        message = str(context.exception)
        self.assertEqual("Template not found", message)
        click_mock.secho.assert_called_with("Publish Failed", fg="red")

    @patch("samcli.commands.publish.command.get_template_data", Mock(return_value={}))
    @patch("serverlessrepo.publish_application")
    @patch("samcli.commands.publish.command.click")
    def test_must_raise_if_serverlessrepo_error(self, click_mock, publish_application_mock):
        publish_application_mock.side_effect = ServerlessRepoError()
        with self.assertRaises(UserException):
            publish_cli(self.ctx_mock, self.template, None)

        click_mock.secho.assert_called_with("Publish Failed", fg="red")

    @patch("samcli.commands.publish.command.get_template_data", Mock(return_value={}))
    @patch("serverlessrepo.publish_application")
    @patch("samcli.commands.publish.command.click")
    def test_must_raise_if_invalid_S3_uri_error(self, click_mock, publish_application_mock):
        publish_application_mock.side_effect = InvalidS3UriError(message="")
        with self.assertRaises(UserException) as context:
            publish_cli(self.ctx_mock, self.template, None)

        message = str(context.exception)
        self.assertTrue("Your SAM template contains invalid S3 URIs" in message)
        click_mock.secho.assert_called_with("Publish Failed", fg="red")

    @patch("samcli.commands.publish.command.get_template_data", Mock(return_value={}))
    @patch("serverlessrepo.publish_application")
    @patch("samcli.commands.publish.command.click")
    def test_must_succeed_to_create_application(self, click_mock, publish_application_mock):
        publish_application_mock.return_value = {
            "application_id": self.application_id,
            "details": {"attr1": "value1"},
            "actions": [CREATE_APPLICATION],
        }

        publish_cli(self.ctx_mock, self.template, None)
        details_str = json.dumps({"attr1": "value1"}, indent=2)
        expected_msg = "Created new application with the following metadata:\n{}"
        expected_link = self.console_link.format(self.ctx_mock.region, self.application_id.replace("/", "~"))
        click_mock.secho.assert_has_calls(
            [
                call("Publish Succeeded", fg="green"),
                call(expected_msg.format(details_str)),
                call(expected_link, fg="yellow"),
            ]
        )

    @patch("samcli.commands.publish.command.get_template_data", Mock(return_value={}))
    @patch("serverlessrepo.publish_application")
    @patch("samcli.commands.publish.command.click")
    def test_must_succeed_to_update_application(self, click_mock, publish_application_mock):
        publish_application_mock.return_value = {
            "application_id": self.application_id,
            "details": {"attr1": "value1"},
            "actions": [UPDATE_APPLICATION],
        }

        publish_cli(self.ctx_mock, self.template, None)
        details_str = json.dumps({"attr1": "value1"}, indent=2)
        expected_msg = 'The following metadata of application "{}" has been updated:\n{}'
        expected_link = self.console_link.format(self.ctx_mock.region, self.application_id.replace("/", "~"))
        click_mock.secho.assert_has_calls(
            [
                call("Publish Succeeded", fg="green"),
                call(expected_msg.format(self.application_id, details_str)),
                call(expected_link, fg="yellow"),
            ]
        )

    @patch("samcli.commands.publish.command.get_template_data", Mock(return_value={}))
    @patch("serverlessrepo.publish_application")
    @patch("samcli.commands.publish.command.boto3")
    @patch("samcli.commands.publish.command.click")
    def test_print_console_link_if_context_region_not_set(self, click_mock, boto3_mock, publish_application_mock):
        self.ctx_mock.region = None
        publish_application_mock.return_value = {
            "application_id": self.application_id,
            "details": {"attr1": "value1"},
            "actions": [UPDATE_APPLICATION],
        }

        session_mock = Mock()
        session_mock.region_name = "us-west-1"
        boto3_mock.Session.return_value = session_mock

        publish_cli(self.ctx_mock, self.template, None)
        expected_link = self.console_link.format(session_mock.region_name, self.application_id.replace("/", "~"))
        click_mock.secho.assert_called_with(expected_link, fg="yellow")

    @patch("samcli.commands.publish.command.get_template_data")
    @patch("serverlessrepo.publish_application")
    def test_must_use_template_semantic_version(self, publish_application_mock, get_template_data_mock):
        template_data = {METADATA: {SERVERLESS_REPO_APPLICATION: {SEMANTIC_VERSION: "0.1"}}}
        get_template_data_mock.return_value = template_data
        publish_application_mock.return_value = {"application_id": self.application_id, "details": {}, "actions": {}}
        publish_cli(self.ctx_mock, self.template, None)
        publish_application_mock.assert_called_with(template_data)

    @patch("samcli.commands.publish.command.get_template_data")
    @patch("serverlessrepo.publish_application")
    def test_must_override_template_semantic_version(self, publish_application_mock, get_template_data_mock):
        template_data = {METADATA: {SERVERLESS_REPO_APPLICATION: {SEMANTIC_VERSION: "0.1"}}}
        get_template_data_mock.return_value = template_data
        publish_application_mock.return_value = {"application_id": self.application_id, "details": {}, "actions": {}}

        publish_cli(self.ctx_mock, self.template, "0.2")
        expected_template_data = {METADATA: {SERVERLESS_REPO_APPLICATION: {SEMANTIC_VERSION: "0.2"}}}
        publish_application_mock.assert_called_with(expected_template_data)
