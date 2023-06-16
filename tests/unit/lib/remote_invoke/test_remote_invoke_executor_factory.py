import itertools
from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.lib.remote_invoke.remote_invoke_executor_factory import (
    RemoteInvokeExecutorFactory,
)
from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeOutputFormat


class TestRemoteInvokeExecutorFactory(TestCase):
    def setUp(self) -> None:
        self.boto_client_provider_mock = Mock()
        self.remote_invoke_executor_factory = RemoteInvokeExecutorFactory(self.boto_client_provider_mock)

    @patch(
        "samcli.lib.remote_invoke.remote_invoke_executor_factory.RemoteInvokeExecutorFactory.REMOTE_INVOKE_EXECUTOR_MAPPING"
    )
    def test_create_remote_invoke_executor(self, patched_executor_mapping):
        given_executor_creator_method = Mock()
        patched_executor_mapping.get.return_value = given_executor_creator_method

        given_executor = Mock()
        given_executor_creator_method.return_value = given_executor

        given_cfn_resource_summary = Mock()
        given_output_format = Mock()
        given_response_consumer = Mock()
        given_log_consumer = Mock()
        executor = self.remote_invoke_executor_factory.create_remote_invoke_executor(
            given_cfn_resource_summary, given_output_format, given_response_consumer, given_log_consumer
        )

        patched_executor_mapping.get.assert_called_with(given_cfn_resource_summary.resource_type)
        given_executor_creator_method.assert_called_with(
            self.remote_invoke_executor_factory,
            given_cfn_resource_summary,
            given_output_format,
            given_response_consumer,
            given_log_consumer,
        )
        self.assertEqual(executor, given_executor)

    def test_failed_create_test_executor(self):
        given_cfn_resource_summary = Mock()
        executor = self.remote_invoke_executor_factory.create_remote_invoke_executor(
            given_cfn_resource_summary, Mock(), Mock(), Mock()
        )
        self.assertIsNone(executor)

    @parameterized.expand(
        itertools.product([True, False], [RemoteInvokeOutputFormat.JSON, RemoteInvokeOutputFormat.TEXT])
    )
    @patch("samcli.lib.remote_invoke.remote_invoke_executor_factory.LambdaInvokeExecutor")
    @patch("samcli.lib.remote_invoke.remote_invoke_executor_factory.LambdaInvokeWithResponseStreamExecutor")
    @patch("samcli.lib.remote_invoke.remote_invoke_executor_factory.DefaultConvertToJSON")
    @patch("samcli.lib.remote_invoke.remote_invoke_executor_factory.LambdaResponseConverter")
    @patch("samcli.lib.remote_invoke.remote_invoke_executor_factory.LambdaStreamResponseConverter")
    @patch("samcli.lib.remote_invoke.remote_invoke_executor_factory.ResponseObjectToJsonStringMapper")
    @patch("samcli.lib.remote_invoke.remote_invoke_executor_factory.RemoteInvokeExecutor")
    @patch("samcli.lib.remote_invoke.remote_invoke_executor_factory._is_function_invoke_mode_response_stream")
    def test_create_lambda_test_executor(
        self,
        is_function_invoke_mode_response_stream,
        remote_invoke_output_format,
        patched_is_function_invoke_mode_response_stream,
        patched_remote_invoke_executor,
        patched_object_to_json_converter,
        patched_stream_response_converter,
        patched_response_converter,
        patched_convert_to_default_json,
        patched_lambda_invoke_with_response_stream_executor,
        patched_lambda_invoke_executor,
    ):
        patched_is_function_invoke_mode_response_stream.return_value = is_function_invoke_mode_response_stream
        given_physical_resource_id = "physical_resource_id"
        given_cfn_resource_summary = Mock(physical_resource_id=given_physical_resource_id)

        given_lambda_client = Mock()
        self.boto_client_provider_mock.return_value = given_lambda_client

        given_remote_invoke_executor = Mock()
        patched_remote_invoke_executor.return_value = given_remote_invoke_executor

        given_response_consumer = Mock()
        given_log_consumer = Mock()
        lambda_executor = self.remote_invoke_executor_factory._create_lambda_boto_executor(
            given_cfn_resource_summary, remote_invoke_output_format, given_response_consumer, given_log_consumer
        )

        self.assertEqual(lambda_executor, given_remote_invoke_executor)
        self.boto_client_provider_mock.assert_called_with("lambda")
        patched_convert_to_default_json.assert_called_once()

        if is_function_invoke_mode_response_stream:
            expected_mappers = []
            if remote_invoke_output_format == RemoteInvokeOutputFormat.JSON:
                patched_object_to_json_converter.assert_called_once()
                patched_stream_response_converter.assert_called_once()
                patched_lambda_invoke_with_response_stream_executor.assert_called_with(
                    given_lambda_client, given_physical_resource_id, remote_invoke_output_format
                )
                expected_mappers = [
                    patched_stream_response_converter(),
                    patched_object_to_json_converter(),
                ]
            patched_remote_invoke_executor.assert_called_with(
                request_mappers=[patched_convert_to_default_json()],
                response_mappers=expected_mappers,
                boto_action_executor=patched_lambda_invoke_with_response_stream_executor(),
                response_consumer=given_response_consumer,
                log_consumer=given_log_consumer,
            )
        else:
            expected_mappers = []
            if remote_invoke_output_format == RemoteInvokeOutputFormat.JSON:
                patched_object_to_json_converter.assert_called_once()
                patched_response_converter.assert_called_once()
                patched_lambda_invoke_executor.assert_called_with(
                    given_lambda_client, given_physical_resource_id, remote_invoke_output_format
                )
                expected_mappers = [
                    patched_response_converter(),
                    patched_object_to_json_converter(),
                ]
            patched_remote_invoke_executor.assert_called_with(
                request_mappers=[patched_convert_to_default_json()],
                response_mappers=expected_mappers,
                boto_action_executor=patched_lambda_invoke_executor(),
                response_consumer=given_response_consumer,
                log_consumer=given_log_consumer,
            )
