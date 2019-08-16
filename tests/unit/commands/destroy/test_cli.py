from unittest import TestCase

from botocore.exceptions import ClientError, WaiterError
from mock import patch, Mock
from samcli.commands.destroy import do_cli as destroy_cli, verify_stack_exists, verify_stack_retain_resources, \
    check_nested_stack


class DestroyTestCalledException(Exception):
    pass


class TestDestroyCli(TestCase):
    def setUp(self):
        self.verify_stack_exists_mock = patch('samcli.commands.destroy.verify_stack_exists', Mock()).start()
        self.verify_stack_retain_resources_mock = patch('samcli.commands.destroy.verify_stack_retain_resources',
                                                        Mock()).start()
        self.check_nested_stack_mock = patch('samcli.commands.destroy.check_nested_stack',
                                             Mock()).start()
        self.mock_client = patch('boto3.client', Mock()).start()
        self.click_secho_mock = patch('click.secho', Mock()).start()

        self.addCleanup(self.verify_stack_exists_mock.stop)
        self.addCleanup(self.verify_stack_retain_resources_mock.stop)
        self.addCleanup(self.mock_client.stop)
        self.addCleanup(self.click_secho_mock.stop)
        self.addCleanup(self.check_nested_stack_mock)

        self.verify_stack_exists_mock.return_value = True
        self.verify_stack_retain_resources_mock.return_value = True

        self.wait_mock = Mock()
        self.wait_mock.wait.return_value = []

        self.get_waiter = Mock()
        self.get_waiter.return_value = self.wait_mock

        self.delete_stack = Mock()
        self.mock_client.return_value = Mock(delete_stack=self.delete_stack, get_waiter=self.get_waiter)
        self.mock_client.delete_stack = self.delete_stack
        self.mock_client.get_waiter = self.get_waiter

    def test_destroy_must_pass_args(self):
        destroy_cli(ctx=None, stack_name='stack-name', force=True)
        self.delete_stack.assert_called_with(StackName="stack-name")

    @patch('click.confirm')
    def test_confirm_cli_printed(self, click_confirm):
        destroy_cli(ctx=None, stack_name='stack-name', force=False)
        click_confirm.assert_called_with('Are you sure you want to delete the stack stack-name?', default=True,
                                         abort=True)

    def test_pass_only_none_null_arguments(self):
        retain_resources = ["testResource"]
        destroy_cli(ctx=None, stack_name='stack-name', retain_resources=retain_resources, force=True)
        self.delete_stack.assert_called_with(StackName="stack-name", RetainResources=retain_resources)

    def test_role_arn_passed(self):
        destroy_cli(ctx=None, stack_name='stack-name', role_arn="testArn", force=True)
        self.delete_stack.assert_called_with(RoleARN='testArn', StackName='stack-name')

    def test_client_request_token(self):
        destroy_cli(ctx=None, stack_name='stack-name', client_request_token="test", force=True)
        self.delete_stack.assert_called_with(ClientRequestToken='test', StackName='stack-name')

    @patch('click.secho')
    @patch('sys.exit')
    def test_termination_protection_enabled(self, exit_client, secho_client):
        self.delete_stack.side_effect = ClientError({"Error": {"Code": 500, "Message": "TerminationProtection"}},
                                                    "Test")
        exit_client.side_effect = DestroyTestCalledException()
        with self.assertRaises(DestroyTestCalledException):
            destroy_cli(ctx=None, stack_name='stack-name', force=True)
        secho_client.assert_called_once_with(
            'The stack stack-name has TerminationProtection turned on. Disable it on the aws console at ' +
            'https://us-west-1.console.aws.amazon.com/cloudformation/home \n or ' +
            'run aws cloudformation update-termination-protection --stack-name stack-name ' +
            '--no-enable-termination-protection',
            fg='red')

    @patch('click.secho')
    @patch('sys.exit')
    def test_access_denied_exception(self, exit_client, secho_client):
        self.delete_stack.side_effect = ClientError({"Error": {"Code": 500, "Message": "AccessDeniedException"}},
                                                    "Test")
        exit_client.side_effect = DestroyTestCalledException()
        with self.assertRaises(DestroyTestCalledException):
            destroy_cli(ctx=None, stack_name='stack-name', force=True)
        secho_client.assert_called_with(
            'The user account does not have access to delete the stack. \n' +
            'Please update the resources required to delete the stack and the required user policies.',
            fg='red')

    @patch('click.secho')
    @patch('sys.exit')
    def test_destroy_unkown_exception(self, exit_client, secho_client):
        self.delete_stack.side_effect = ClientError({"Error": {"Code": 500, "Message": "UNKOWN_EXCEPTION"}},
                                                    "Test")
        exit_client.side_effect = DestroyTestCalledException()
        with self.assertRaises(DestroyTestCalledException):
            destroy_cli(ctx=None, stack_name='stack-name', force=True)
        secho_client.assert_called_with('Failed to destroy Stack: UNKOWN_EXCEPTION', fg='red')

    def test_destroy_wait_called(self):
        destroy_cli(ctx=None, stack_name='stack-name', wait=True, wait_time=100, force=True)
        self.wait_mock.wait.assert_called_with(StackName='stack-name',
                                               WaiterConfig={'Delay': 15, 'MaxAttemps': int(100 / 15)})

    @patch('click.secho')
    @patch('sys.exit')
    def test_destroy_wait_called_error(self, exit_client, secho_client):
        exit_client.side_effect = DestroyTestCalledException()
        self.wait_mock.wait.side_effect = WaiterError("name", "reason", "last_response")
        with self.assertRaises(DestroyTestCalledException):
            destroy_cli(ctx=None, stack_name='stack-name', wait=True, wait_time=100, force=True)
        secho_client.assert_called_with('Failed to delete stack stack-name because Waiter name failed: reason',
                                        fg='red')


class TestDestroyStackVerification(TestCase):
    @patch('boto3.client')
    def test_verify_stack_exists(self, client):
        describe_stacks = Mock()
        client.return_value = Mock(describe_stacks=describe_stacks)
        client.describe_stacks = describe_stacks

        verify_stack_exists(client, 'stack-name')
        describe_stacks.assert_called_with(StackName='stack-name')

    @patch('boto3.client')
    @patch('click.secho')
    @patch('sys.exit')
    def test_verify_stack_exists_with_status(self, sys_exit, click_client, boto_client):
        describe_stacks = Mock()
        describe_stacks.return_value = {
            'Stacks': [
                {'StackStatus': 'HEALTHY'}
            ]
        }
        boto_client.return_value = Mock()
        boto_client.describe_stacks = describe_stacks

        verify_stack_exists(boto_client, 'stack-name', required_status="HEALTHY")
        describe_stacks.assert_called_with(StackName='stack-name')

    @patch('boto3.client')
    @patch('click.secho')
    @patch('sys.exit')
    def test_verify_stack_exists_with_status_fail(self, sys_exit, click_client, boto_client):
        sys_exit.return_value = True
        describe_stacks = Mock()
        describe_stacks.return_value = {
            'Stacks': [
                {'StackStatus': 'UNHEALTHY VERY UNHEALTHY'}
            ]
        }
        boto_client.return_value = Mock()
        boto_client.describe_stacks = describe_stacks

        verify_stack_exists(boto_client, 'stack-name', required_status="HEALTHY")
        click_client.assert_called_with('The stack stack-name does not have the correct status HEALTHY', fg='red')

    @patch('boto3.client')
    @patch('click.secho')
    @patch('sys.exit')
    def test_failure_stack_exists(self, sys_exit, click_client, boto_client):
        describe_stacks = Mock()
        describe_stacks.side_effect = ClientError({}, "Test")
        boto_client.return_value = Mock()
        boto_client.describe_stacks = describe_stacks

        verify_stack_exists(boto_client, 'stack-name')
        click_client.assert_called_with('The stack stack-name must exist in order to be deleted', fg='red')

    @patch('boto3.client')
    @patch('sys.exit')
    def test_verify_stack_retain_resources_paginates(self, sys_exit, client):
        paginator = Mock()
        paginator.paginate.return_value = \
            [{
                "StackEvents": [{
                    "LogicalResourceId": "test",
                    "ResourceStatus": "Success"
                }, {
                    "LogicalResourceId": "test",
                    "ResourceStatus": "DELETE_FAILED"
                }, ]
            }]

        get_paginator = Mock()
        get_paginator.return_value = paginator

        client.return_value = Mock()
        client.get_paginator = get_paginator

        verify_stack_retain_resources(client, 'stack-name', retain_resources=["test"])
        sys_exit.assert_not_called()

    @patch('boto3.client')
    @patch('click.secho')
    @patch('sys.exit')
    def test_verify_stack_retain_resources_paginates_fail(self, sys_exit, secho_client, client):
        paginator = Mock()
        paginator.paginate.return_value = \
            [{
                "StackEvents": [{
                    "LogicalResourceId": "test",
                    "ResourceStatus": "Success"
                }, {
                    "LogicalResourceId": "test",
                    "ResourceStatus": "DELETE_FAILED"
                }, ]
            }]

        get_paginator = Mock()
        get_paginator.return_value = paginator

        client.return_value = Mock()
        client.get_paginator = get_paginator

        verify_stack_retain_resources(client, 'stack-name')
        secho_client.assert_called_with(
            "The logicalId test of the resource in the stack stack-name failed to delete. You'll need to resolve the"
            " root cause of the failure to delete this resource or add it to the set of retained resources in order"
            " to complete deletion of your stack.",
            fg='red')
        sys_exit.assert_called_with(1)

    @patch('boto3.client')
    @patch('click.confirm')
    def test_check_nested_stack(self, confirm_client, boto_client):
        boto_client.get_template.return_value = {
            "Resources": {
                "NestedStack": {
                    "Type": "AWS::CloudFormation::Stack",
                    "Test": "test"
                },
                "Other Item": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "StageName": "Prod"
                    }
                }
            }
        }
        check_nested_stack(boto_client, 'stack-name')
        confirm_client.assert_called_with(
            "The stack stack-name is a nested stack with the following resources: ['NestedStack']."
            " Are you want to destroy them?",
            abort=True, default=True)
