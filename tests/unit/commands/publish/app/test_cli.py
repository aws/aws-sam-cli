"""Test sam publish app CLI."""
import json
from unittest import TestCase
from mock import patch, call, Mock

from botocore.exceptions import ClientError

from serverlessrepo.exceptions import ServerlessRepoError
from serverlessrepo.publish import CREATE_APPLICATION, UPDATE_APPLICATION

from samcli.commands.publish.app.cli import do_cli as publish_app_cli
from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException
from samcli.commands.exceptions import UserException


class TestCli(TestCase):

    def setUp(self):
        self.template = "./template"
        self.application_id = "arn:aws:serverlessrepo:us-east-1:123456789012:applications/hello"
        self.ctx_mock = Mock()
        self.ctx_mock.region = "us-east-1"
        self.console_link = "Click the link below to view your application in AWS console:\n" \
            "https://console.aws.amazon.com/serverlessrepo/home?region={}#/published-applications/{}"

        path_patcher = patch('samcli.commands.publish.app.cli.os.path')
        self.path_mock = path_patcher.start()
        self.path_mock.exists.return_value = True

        click_patcher = patch('samcli.commands.publish.app.cli.click')
        self.click_mock = click_patcher.start()
        fs_mock = Mock()
        fs_mock.read.return_value = "hello"
        self.click_mock.open_file.__enter__.return_value = fs_mock

        self.addCleanup(patch.stopall)

    def test_must_raise_if_no_template_found(self):
        self.path_mock.exists.return_value = False
        with self.assertRaises(SamTemplateNotFoundException) as context:
            publish_app_cli(self.ctx_mock, self.template)

        msg = str(context.exception)
        expected = "Template at {} is not found".format(self.template)
        self.assertEqual(msg, expected)
        self.click_mock.secho.assert_called_with("Publish Failed", fg="red")

    @patch('samcli.commands.publish.app.cli.publish_application')
    def test_must_raise_if_serverlessrepo_error(self, publish_application_mock):
        publish_application_mock.side_effect = ServerlessRepoError()
        with self.assertRaises(UserException):
            publish_app_cli(self.ctx_mock, self.template)

        self.click_mock.secho.assert_called_with("Publish Failed", fg="red")

    @patch('samcli.commands.publish.app.cli.publish_application')
    def test_must_raise_if_s3_uri_error(self, publish_application_mock):
        publish_application_mock.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'BadRequestException',
                    'Message': 'Invalid S3 URI'
                }
            },
            'create_application'
        )
        with self.assertRaises(UserException) as context:
            publish_app_cli(self.ctx_mock, self.template)

        message = str(context.exception)
        self.assertIn("Please make sure that you have uploaded application artifacts "
                      "to S3 by packaging the template", message)
        self.click_mock.secho.assert_called_with("Publish Failed", fg="red")

    @patch('samcli.commands.publish.app.cli.publish_application')
    def test_must_raise_if_not_s3_uri_error(self, publish_application_mock):
        publish_application_mock.side_effect = ClientError(
            {'Error': {'Code': 'OtherError', 'Message': 'OtherMessage'}},
            'other_operation'
        )
        with self.assertRaises(ClientError):
            publish_app_cli(self.ctx_mock, self.template)

        self.click_mock.secho.assert_called_with("Publish Failed", fg="red")

    @patch('samcli.commands.publish.app.cli.publish_application')
    def test_must_succeed_to_create_application(self, publish_application_mock):
        publish_application_mock.return_value = {
            'application_id': self.application_id,
            'details': {'attr1': 'value1'},
            'actions': [CREATE_APPLICATION]
        }

        publish_app_cli(self.ctx_mock, self.template)
        details_str = json.dumps({'attr1': 'value1'}, indent=2)
        expected_msg = "Created new application with the following metadata:\n{}"
        expected_link = self.console_link.format(
            self.ctx_mock.region,
            self.application_id.replace('/', '~')
        )
        self.click_mock.secho.assert_has_calls([
            call("Publish Succeeded", fg="green"),
            call(expected_msg.format(details_str), fg="yellow"),
            call(expected_link, fg="yellow")
        ])

    @patch('samcli.commands.publish.app.cli.publish_application')
    def test_must_succeed_to_update_application(self, publish_application_mock):
        publish_application_mock.return_value = {
            'application_id': self.application_id,
            'details': {'attr1': 'value1'},
            'actions': [UPDATE_APPLICATION]
        }

        publish_app_cli(self.ctx_mock, self.template)
        details_str = json.dumps({'attr1': 'value1'}, indent=2)
        expected_msg = 'The following metadata of application "{}" has been updated:\n{}'
        expected_link = self.console_link.format(
            self.ctx_mock.region,
            self.application_id.replace('/', '~')
        )
        self.click_mock.secho.assert_has_calls([
            call("Publish Succeeded", fg="green"),
            call(expected_msg.format(self.application_id, details_str), fg="yellow"),
            call(expected_link, fg="yellow")
        ])
