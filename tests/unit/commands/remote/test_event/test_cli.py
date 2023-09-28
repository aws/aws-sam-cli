import click
from unittest import TestCase
from unittest.mock import patch, Mock, PropertyMock, mock_open
from parameterized import parameterized
import tempfile

from samcli.commands.remote.test_event.delete.cli import do_cli as do_delete_cli
from samcli.commands.remote.test_event.get.cli import do_cli as do_get_cli
from samcli.commands.remote.test_event.put.cli import do_cli as do_put_cli
from samcli.commands.remote.test_event.list.cli import do_cli as do_list_cli

from samcli.lib.remote_invoke.exceptions import (
    ErrorBotoApiCallException,
    InvalideBotoResponseException,
    InvalidResourceBotoParameterException,
)

from samcli.commands.exceptions import UserException
from samcli.commands.remote.exceptions import InvalidEventOutputFile, IllFormedEventData


class TestRemoteTestEventCliCommand(TestCase):
    def setUp(self) -> None:
        self.stack_name = "stack_name"
        self.resource_id = "resource_id"
        self.region = "region"
        self.profile = "profile"
        self.config_file = "config_file"
        self.config_env = "config_env"
        self.name = "MyEvent"

    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    def test_remote_test_event_delete_command(
        self,
        mock_remote_invoke_context,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        context_mock = Mock()
        test_event_mock = Mock()
        context_mock.get_lambda_shared_test_event_provider.return_value = test_event_mock
        mock_remote_invoke_context.return_value.__enter__.return_value = context_mock

        function_resource = Mock()
        context_mock.resource_summary = function_resource

        do_delete_cli(
            stack_name=self.stack_name,
            resource_id=self.resource_id,
            event_name=self.name,
            region=self.region,
            profile=self.profile,
            config_file=self.config_file,
            config_env=self.config_env,
        )

        mock_remote_invoke_context.assert_called_with(
            boto_client_provider=given_client_provider,
            boto_resource_provider=given_resource_provider,
            stack_name=self.stack_name,
            resource_id=self.resource_id,
        )

        test_event_mock.delete_event.assert_called_with(self.name, function_resource)

    @parameterized.expand(
        [
            (InvalideBotoResponseException,),
            (ErrorBotoApiCallException,),
            (InvalidResourceBotoParameterException,),
        ]
    )
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    def test_raise_user_exception_delete_not_successfull(
        self,
        exeception_to_raise,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
        mock_invoke_context,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        context_mock = Mock()
        mock_invoke_context.return_value.__enter__.return_value = context_mock
        resource_mock = PropertyMock(side_effect=exeception_to_raise)
        type(context_mock).resource_summary = resource_mock

        with self.assertRaises(UserException):
            do_delete_cli(
                stack_name=None,
                resource_id="mock-resource-id",
                event_name="event",
                region=self.region,
                profile=self.profile,
                config_file=self.config_file,
                config_env=self.config_env,
            )

    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    def test_remote_test_event_get_command_file(
        self,
        mock_remote_invoke_context,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        context_mock = Mock()
        test_event_mock = Mock()
        context_mock.get_lambda_shared_test_event_provider.return_value = test_event_mock
        mock_remote_invoke_context.return_value.__enter__.return_value = context_mock

        test_event_mock.get_event.return_value = "placeholderstring"

        function_resource = Mock()
        context_mock.resource_summary = function_resource

        with tempfile.NamedTemporaryFile("w+") as temp:
            do_get_cli(
                stack_name=None,
                resource_id="mock-resource-id",
                name=self.name,
                output_file=temp,
                region=self.region,
                profile=self.profile,
                config_file=self.config_file,
                config_env=self.config_env,
            )

            test_event_mock.get_event.assert_called_once_with(self.name, function_resource)

            temp.flush()
            temp.seek(0)
            data = temp.read()

            self.assertEqual("placeholderstring", data)

    @parameterized.expand(
        [
            (InvalideBotoResponseException,),
            (ErrorBotoApiCallException,),
            (InvalidResourceBotoParameterException,),
        ]
    )
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    def test_raise_user_exception_get_not_successfull(
        self,
        exeception_to_raise,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
        mock_invoke_context,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        context_mock = Mock()
        mock_invoke_context.return_value.__enter__.return_value = context_mock
        resource_mock = PropertyMock(side_effect=exeception_to_raise)
        type(context_mock).resource_summary = resource_mock

        with self.assertRaises(UserException):
            do_get_cli(
                stack_name=None,
                resource_id="mock-resource-id",
                name="event",
                output_file="foo",
                region=self.region,
                profile=self.profile,
                config_file=self.config_file,
                config_env=self.config_env,
            )

    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    def test_remote_test_event_get_file_error(
        self,
        mock_remote_invoke_context,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        context_mock = Mock()
        test_event_mock = Mock()
        context_mock.get_lambda_shared_test_event_provider.return_value = test_event_mock
        mock_remote_invoke_context.return_value.__enter__.return_value = context_mock

        test_event_mock.get_event.return_value = "placeholderstring"

        context_mock.resource_summary = Mock()

        file_with_error = Mock()
        file_with_error.write.side_effect = click.FileError("wrongfilename")

        with self.assertRaises(InvalidEventOutputFile):
            do_get_cli(
                stack_name=None,
                resource_id="mock-resource-id",
                name="event",
                output_file=file_with_error,
                region=self.region,
                profile=self.profile,
                config_file=self.config_file,
                config_env=self.config_env,
            )

    @patch("samcli.commands.remote.test_event.put.cli.yaml_parse")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    def test_remote_test_event_put_command(
        self,
        mock_remote_invoke_context,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
        patched_yaml_parse,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        context_mock = Mock()
        test_event_mock = Mock()
        context_mock.get_lambda_shared_test_event_provider.return_value = test_event_mock
        mock_remote_invoke_context.return_value.__enter__.return_value = context_mock

        function_resource = Mock()
        context_mock.resource_summary = function_resource
        patched_yaml_parse.return_value = {"foo": "bar"}

        do_put_cli(
            stack_name=self.stack_name,
            resource_id=self.resource_id,
            name=self.name,
            file=Mock(),
            force=False,
            region=self.region,
            profile=self.profile,
            config_file=self.config_file,
            config_env=self.config_env,
        )

        mock_remote_invoke_context.assert_called_with(
            boto_client_provider=given_client_provider,
            boto_resource_provider=given_resource_provider,
            stack_name=self.stack_name,
            resource_id=self.resource_id,
        )

        test_event_mock.create_event.assert_called_with(self.name, function_resource, '{"foo": "bar"}', force=False)

    @parameterized.expand(
        [
            (InvalideBotoResponseException,),
            (ErrorBotoApiCallException,),
            (InvalidResourceBotoParameterException,),
        ]
    )
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    def test_raise_user_exception_put_not_successfull(
        self,
        exeception_to_raise,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
        mock_invoke_context,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        context_mock = Mock()
        mock_invoke_context.return_value.__enter__.return_value = context_mock
        resource_mock = PropertyMock(side_effect=exeception_to_raise)
        type(context_mock).resource_summary = resource_mock

        with self.assertRaises(UserException):
            do_put_cli(
                stack_name=None,
                resource_id="mock-resource-id",
                name="event",
                file="foo",
                force=False,
                region=self.region,
                profile=self.profile,
                config_file=self.config_file,
                config_env=self.config_env,
            )

    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    def test_put_fails_when_empty(
        self,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
        mock_invoke_context,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        context_mock = Mock()
        test_event_mock = Mock()
        context_mock.get_lambda_shared_test_event_provider.return_value = test_event_mock
        mock_invoke_context.return_value.__enter__.return_value = context_mock

        empty_file = Mock()
        empty_file.read.return_value = ""

        with self.assertRaises(IllFormedEventData):
            do_put_cli(
                stack_name=None,
                resource_id="mock-resource-id",
                name="event",
                file=empty_file,
                force=False,
                region=self.region,
                profile=self.profile,
                config_file=self.config_file,
                config_env=self.config_env,
            )

    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    def test_put_fails_when_json_error(
        self,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
        mock_invoke_context,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        context_mock = Mock()
        test_event_mock = Mock()
        context_mock.get_lambda_shared_test_event_provider.return_value = test_event_mock
        mock_invoke_context.return_value.__enter__.return_value = context_mock

        empty_file = Mock()
        empty_file.read.return_value = "{error not a json}}"

        with self.assertRaises(IllFormedEventData):
            do_put_cli(
                stack_name=None,
                resource_id="mock-resource-id",
                name="event",
                file=empty_file,
                force=False,
                region=self.region,
                profile=self.profile,
                config_file=self.config_file,
                config_env=self.config_env,
            )

    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    def test_remote_test_event_list_command(
        self,
        mock_remote_invoke_context,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        context_mock = Mock()
        test_event_mock = Mock()
        context_mock.get_lambda_shared_test_event_provider.return_value = test_event_mock
        mock_remote_invoke_context.return_value.__enter__.return_value = context_mock

        function_resource = Mock()
        context_mock.resource_summary = function_resource

        do_list_cli(
            stack_name=self.stack_name,
            resource_id=self.resource_id,
            region=self.region,
            profile=self.profile,
            config_file=self.config_file,
            config_env=self.config_env,
        )

        test_event_mock.list_events.assert_called_with(function_resource)
