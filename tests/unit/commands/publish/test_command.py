"""Test sam publish CLI."""
import json
from unittest import TestCase
from mock import patch, call, Mock

from botocore.exceptions import ClientError
from serverlessrepo.exceptions import ServerlessRepoError
from serverlessrepo.publish import CREATE_APPLICATION, UPDATE_APPLICATION

from samcli.commands.publish.command import do_cli as publish_cli
from samcli.commands.exceptions import UserException


class TestCli(TestCase):

    def setUp(self):
        self.template = "./template"
        self.application_id = "arn:aws:serverlessrepo:us-east-1:123456789012:applications/hello"
        self.ctx_mock = Mock()
        self.ctx_mock.region = "us-east-1"
        self.console_link = "Click the link below to view your application in AWS console:\n" \
            "https://console.aws.amazon.com/serverlessrepo/home?region={}#/published-applications/{}"

    @patch('samcli.commands.publish.command.get_template_data')
    @patch('samcli.commands.publish.command.click')
    def test_must_raise_if_value_error(self, click_mock, get_template_data_mock):
        get_template_data_mock.side_effect = ValueError("Template not found")
        with self.assertRaises(UserException) as context:
            publish_cli(self.ctx_mock, self.template)

        message = str(context.exception)
        self.assertEqual("Template not found", message)
        click_mock.secho.assert_called_with("Publish Failed", fg="red")

    @patch('samcli.commands.publish.command.get_template_data', Mock(return_value={}))
    @patch('samcli.commands.publish.command.publish_application')
    @patch('samcli.commands.publish.command.click')
    def test_must_raise_if_serverlessrepo_error(self, click_mock, publish_application_mock):
        publish_application_mock.side_effect = ServerlessRepoError()
        with self.assertRaises(UserException):
            publish_cli(self.ctx_mock, self.template)

        click_mock.secho.assert_called_with("Publish Failed", fg="red")

    @patch('samcli.commands.publish.command.get_template_data', Mock(return_value={}))
    @patch('samcli.commands.publish.command.publish_application')
    @patch('samcli.commands.publish.command.click')
    def test_must_raise_if_s3_uri_error(self, click_mock, publish_application_mock):
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
            publish_cli(self.ctx_mock, self.template)

        message = str(context.exception)
        self.assertIn("Please make sure that you have uploaded application artifacts "
                      "to S3 by packaging the template", message)
        click_mock.secho.assert_called_with("Publish Failed", fg="red")

    @patch('samcli.commands.publish.command.get_template_data', Mock(return_value={}))
    @patch('samcli.commands.publish.command.publish_application')
    @patch('samcli.commands.publish.command.click')
    def test_must_raise_if_not_s3_uri_error(self, click_mock, publish_application_mock):
        publish_application_mock.side_effect = ClientError(
            {'Error': {'Code': 'OtherError', 'Message': 'OtherMessage'}},
            'other_operation'
        )
        with self.assertRaises(ClientError):
            publish_cli(self.ctx_mock, self.template)

        click_mock.secho.assert_called_with("Publish Failed", fg="red")

    @patch('samcli.commands.publish.command.get_template_data', Mock(return_value={}))
    @patch('samcli.commands.publish.command.publish_application')
    @patch('samcli.commands.publish.command.click')
    def test_must_succeed_to_create_application(self, click_mock, publish_application_mock):
        publish_application_mock.return_value = {
            'application_id': self.application_id,
            'details': {'attr1': 'value1'},
            'actions': [CREATE_APPLICATION]
        }

        publish_cli(self.ctx_mock, self.template)
        details_str = json.dumps({'attr1': 'value1'}, indent=2)
        expected_msg = "Created new application with the following metadata:\n{}"
        expected_link = self.console_link.format(
            self.ctx_mock.region,
            self.application_id.replace('/', '~')
        )
        click_mock.secho.assert_has_calls([
            call("Publish Succeeded", fg="green"),
            call(expected_msg.format(details_str), fg="yellow"),
            call(expected_link, fg="yellow")
        ])

    @patch('samcli.commands.publish.command.get_template_data', Mock(return_value={}))
    @patch('samcli.commands.publish.command.publish_application')
    @patch('samcli.commands.publish.command.click')
    def test_must_succeed_to_update_application(self, click_mock, publish_application_mock):
        publish_application_mock.return_value = {
            'application_id': self.application_id,
            'details': {'attr1': 'value1'},
            'actions': [UPDATE_APPLICATION]
        }

        publish_cli(self.ctx_mock, self.template)
        details_str = json.dumps({'attr1': 'value1'}, indent=2)
        expected_msg = 'The following metadata of application "{}" has been updated:\n{}'
        expected_link = self.console_link.format(
            self.ctx_mock.region,
            self.application_id.replace('/', '~')
        )
        click_mock.secho.assert_has_calls([
            call("Publish Succeeded", fg="green"),
            call(expected_msg.format(self.application_id, details_str), fg="yellow"),
            call(expected_link, fg="yellow")
        ])

    @patch('samcli.commands.publish.command.get_template_data', Mock(return_value={}))
    @patch('samcli.commands.publish.command.publish_application')
    @patch('samcli.commands.publish.command.boto3')
    @patch('samcli.commands.publish.command.click')
    def test_print_console_link_if_context_region_not_set(self, click_mock, boto3_mock,
                                                          publish_application_mock):
        self.ctx_mock.region = None
        publish_application_mock.return_value = {
            'application_id': self.application_id,
            'details': {'attr1': 'value1'},
            'actions': [UPDATE_APPLICATION]
        }

        session_mock = Mock()
        session_mock.region_name = "us-west-1"
        boto3_mock.Session.return_value = session_mock

        publish_cli(self.ctx_mock, self.template)
        expected_link = self.console_link.format(
            session_mock.region_name,
            self.application_id.replace('/', '~')
        )
        click_mock.secho.assert_called_with(expected_link, fg="yellow")
