from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.commands.remote.invoke.cli import do_cli
from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeOutputFormat
from samcli.lib.remote_invoke.exceptions import (
    ErrorBotoApiCallException,
    InvalideBotoResponseException,
    InvalidResourceBotoParameterException,
)
from samcli.commands.exceptions import UserException


class TestRemoteInvokeCliCommand(TestCase):
    def setUp(self) -> None:
        self.stack_name = "stack_name"
        self.resource_id = "resource_id"
        self.region = "region"
        self.profile = "profile"
        self.config_file = "config_file"
        self.config_env = "config_env"

    @parameterized.expand(
        [
            ("event", None, RemoteInvokeOutputFormat.TEXT, {}, "log-output"),
            ("event", None, RemoteInvokeOutputFormat.TEXT, {}, None),
            ("event", None, RemoteInvokeOutputFormat.TEXT, {"Param1": "ParamValue1"}, "log-output"),
            ("event", None, RemoteInvokeOutputFormat.JSON, {}, None),
            ("event", None, RemoteInvokeOutputFormat.JSON, {"Param1": "ParamValue1"}, "log-output"),
            ("event", None, RemoteInvokeOutputFormat.JSON, {"Param1": "ParamValue1"}, None),
            (None, "event_file", RemoteInvokeOutputFormat.TEXT, {"Param1": "ParamValue1"}, None),
            (None, "event_file", RemoteInvokeOutputFormat.JSON, {"Param1": "ParamValue1"}, "log-output"),
        ]
    )
    @patch("samcli.lib.remote_invoke.remote_invoke_executors.RemoteInvokeExecutionInfo")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    def test_remote_invoke_command(
        self,
        event,
        event_file,
        output,
        parameter,
        log_output,
        mock_remote_invoke_context,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
        patched_remote_invoke_execution_info,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        given_remote_invoke_execution_info = Mock()
        patched_remote_invoke_execution_info.return_value = given_remote_invoke_execution_info

        stdout_stream_writer_mock = Mock()
        stderr_stream_writer_mock = Mock()

        context_mock = Mock()
        mock_remote_invoke_context.return_value.__enter__.return_value = context_mock
        context_mock.stdout = stdout_stream_writer_mock
        context_mock.stderr = stderr_stream_writer_mock

        given_remote_invoke_result = Mock()
        given_remote_invoke_result.is_succeeded.return_value = True
        given_remote_invoke_result.log_output = log_output
        context_mock.run.return_value = given_remote_invoke_result

        do_cli(
            stack_name=self.stack_name,
            resource_id=self.resource_id,
            event=event,
            event_file=event_file,
            parameter=parameter,
            output=output,
            region=self.region,
            profile=self.profile,
            config_file=self.config_file,
            config_env=self.config_env,
        )

        patched_get_boto_client_provider_with_config.assert_called_with(region_name=self.region)
        patched_get_boto_resource_provider_with_config.assert_called_with(region_name=self.region)

        mock_remote_invoke_context.assert_called_with(
            boto_client_provider=given_client_provider,
            boto_resource_provider=given_resource_provider,
            stack_name=self.stack_name,
            resource_id=self.resource_id,
        )

        patched_remote_invoke_execution_info.assert_called_with(
            payload=event, payload_file=event_file, parameters=parameter, output_format=output
        )

        context_mock.run.assert_called_with(remote_invoke_input=given_remote_invoke_execution_info)

    @parameterized.expand(
        [
            (InvalideBotoResponseException,),
            (ErrorBotoApiCallException,),
            (InvalidResourceBotoParameterException,),
        ]
    )
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    def test_raise_user_exception_invoke_not_successfull(self, exeception_to_raise, mock_invoke_context):
        context_mock = Mock()
        mock_invoke_context.return_value.__enter__.return_value = context_mock
        context_mock.run.side_effect = exeception_to_raise

        with self.assertRaises(UserException):
            do_cli(
                stack_name=None,
                resource_id="mock-resource-id",
                event="event",
                event_file=None,
                parameter={},
                output=RemoteInvokeOutputFormat.TEXT,
                region=self.region,
                profile=self.profile,
                config_file=self.config_file,
                config_env=self.config_env,
            )
