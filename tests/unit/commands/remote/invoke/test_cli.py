from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from botocore.exceptions import (
    ProfileNotFound,
    NoCredentialsError,
    NoRegionError,
)
from samcli.commands.remote.invoke.cli import do_cli
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION, AWS_STEPFUNCTIONS_STATEMACHINE
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
    @patch("samcli.lib.telemetry.event.EventTracker.track_event")
    def test_remote_invoke_command(
        self,
        event,
        event_file,
        output,
        parameter,
        log_output,
        mock_track_event,
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

        tracked_events = []

        def mock_tracker(name, value):  # when track_event is called, append an equivalent event to our list
            tracked_events.append([name, value])

        mock_track_event.side_effect = mock_tracker

        do_cli(
            stack_name=self.stack_name,
            resource_id=self.resource_id,
            event=event,
            event_file=event_file,
            parameter=parameter,
            output=output,
            test_event_name=None,
            region=self.region,
            profile=self.profile,
            config_file=self.config_file,
            config_env=self.config_env,
        )

        patched_get_boto_client_provider_with_config.assert_called_with(region_name=self.region, profile=self.profile)
        patched_get_boto_resource_provider_with_config.assert_called_with(region_name=self.region, profile=self.profile)

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
        # Not using Lambda remote test events
        context_mock.get_lambda_shared_test_event_provider.assert_not_called()

        # Assert right metric was emitted
        expected_metric = "text" if event else "file"
        self.assertIn(["RemoteInvokeEventType", expected_metric], tracked_events)

    @patch("samcli.lib.remote_invoke.remote_invoke_executors.RemoteInvokeExecutionInfo")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    @patch("samcli.lib.telemetry.event.EventTracker.track_event")
    def test_remote_invoke_with_shared_test_event_command(
        self,
        mock_track_event,
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

        context_mock = Mock()
        test_event_mock = Mock()
        test_event_mock.get_event.return_value = "stuff"
        fn_resource = Mock()
        fn_resource.resource_type = AWS_LAMBDA_FUNCTION
        context_mock.resource_summary = fn_resource
        context_mock.get_lambda_shared_test_event_provider.return_value = test_event_mock
        mock_remote_invoke_context.return_value.__enter__.return_value = context_mock

        given_remote_invoke_result = Mock()
        given_remote_invoke_result.is_succeeded.return_value = True
        given_remote_invoke_result.log_output = "log_output"
        context_mock.run.return_value = given_remote_invoke_result

        tracked_events = []

        def mock_tracker(name, value):  # when track_event is called, append an equivalent event to our list
            tracked_events.append([name, value])

        mock_track_event.side_effect = mock_tracker

        do_cli(
            stack_name=self.stack_name,
            resource_id=self.resource_id,
            event=None,
            event_file=None,
            parameter={},
            output=RemoteInvokeOutputFormat.TEXT,
            test_event_name="event1",
            region=self.region,
            profile=self.profile,
            config_file=self.config_file,
            config_env=self.config_env,
        )

        test_event_mock.get_event.assert_called_with("event1", fn_resource)
        patched_remote_invoke_execution_info.assert_called_with(
            payload="stuff",
            payload_file=None,
            parameters={},
            output_format=RemoteInvokeOutputFormat.TEXT,
        )
        context_mock.run.assert_called_with(remote_invoke_input=given_remote_invoke_execution_info)
        # Assert metric was emitted
        self.assertIn(["RemoteInvokeEventType", "remote_event"], tracked_events)

    @patch("samcli.lib.remote_invoke.remote_invoke_executors.RemoteInvokeExecutionInfo")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    @patch("samcli.commands.remote.remote_invoke_context.RemoteInvokeContext")
    @patch("samcli.lib.telemetry.event.EventTracker.track_event")
    def test_remote_invoke_with_shared_test_and_event_for_non_supported_resource_event_command(
        self,
        mock_track_event,
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

        context_mock = Mock()
        fn_resource = Mock()
        fn_resource.resource_type = AWS_STEPFUNCTIONS_STATEMACHINE
        context_mock.resource_summary = fn_resource
        mock_remote_invoke_context.return_value.__enter__.return_value = context_mock

        given_remote_invoke_result = Mock()
        given_remote_invoke_result.is_succeeded.return_value = True
        given_remote_invoke_result.log_output = "log_output"
        context_mock.run.return_value = given_remote_invoke_result

        tracked_events = []

        def mock_tracker(name, value):  # when track_event is called, append an equivalent event to our list
            tracked_events.append([name, value])

        mock_track_event.side_effect = mock_tracker

        do_cli(
            stack_name=self.stack_name,
            resource_id=self.resource_id,
            event="Hello world",
            event_file=None,
            parameter={},
            output=RemoteInvokeOutputFormat.TEXT,
            test_event_name="event1",
            region=self.region,
            profile=self.profile,
            config_file=self.config_file,
            config_env=self.config_env,
        )

        patched_remote_invoke_execution_info.assert_called_with(
            payload="Hello world",
            payload_file=None,
            parameters={},
            output_format=RemoteInvokeOutputFormat.TEXT,
        )
        context_mock.run.assert_called_with(remote_invoke_input=given_remote_invoke_execution_info)
        # Assert metric was emitted
        self.assertIn(["RemoteInvokeEventType", "text"], tracked_events)

    @parameterized.expand(
        [
            (InvalideBotoResponseException,),
            (ErrorBotoApiCallException,),
            (InvalidResourceBotoParameterException,),
            (ProfileNotFound,),
            (NoCredentialsError,),
            (NoRegionError,),
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
                test_event_name=None,
                region=self.region,
                profile=self.profile,
                config_file=self.config_file,
                config_env=self.config_env,
            )
