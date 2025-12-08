import base64
import json
from abc import ABC, abstractmethod
from io import BytesIO
from typing import Any
from unittest import TestCase
from unittest.mock import Mock, patch

from parameterized import parameterized

from samcli.lib.remote_invoke.lambda_invoke_executors import (
    EVENT_STREAM,
    INVOKE_COMPLETE,
    LOG_RESULT,
    PAYLOAD,
    PAYLOAD_CHUNK,
    AbstractLambdaInvokeExecutor,
    ClientError,
    DefaultConvertToJSON,
    DurableFunctionQualifierMapper,
    ErrorBotoApiCallException,
    InvalideBotoResponseException,
    InvalidResourceBotoParameterException,
    LambdaInvokeExecutor,
    LambdaInvokeWithResponseStreamExecutor,
    LambdaResponseConverter,
    LambdaStreamResponseConverter,
    ParamValidationError,
    RemoteInvokeOutputFormat,
    _is_durable_function,
    _is_function_invoke_mode_response_stream,
)
from samcli.lib.remote_invoke.remote_invoke_executors import (
    RemoteInvokeExecutionInfo,
    RemoteInvokeLogOutput,
    RemoteInvokeResponse,
)


class CommonTestsLambdaInvokeExecutor:
    class AbstractLambdaInvokeExecutorTest(ABC, TestCase):
        lambda_client: Any
        lambda_invoke_executor: AbstractLambdaInvokeExecutor

        @abstractmethod
        def _get_boto3_method(self):
            pass

        @parameterized.expand(
            [
                ("ValidationException",),
                ("InvalidRequestContentException",),
            ]
        )
        def test_execute_action_invalid_parameter_value_throws_client_error(self, error_code):
            given_payload = Mock()
            error = ClientError(error_response={"Error": {"Code": error_code}}, operation_name="invoke")
            self._get_boto3_method().side_effect = error
            with self.assertRaises(InvalidResourceBotoParameterException):
                for _ in self.lambda_invoke_executor._execute_action(given_payload):
                    pass

        def test_execute_action_invalid_parameter_key_throws_parameter_validation_exception(self):
            given_payload = Mock()
            error = ParamValidationError(report="Invalid parameters")
            self._get_boto3_method().side_effect = error
            with self.assertRaises(InvalidResourceBotoParameterException):
                for _ in self.lambda_invoke_executor._execute_action(given_payload):
                    pass

        def test_execute_action_throws_client_error_exception(self):
            given_payload = "payload"
            error = ClientError(error_response={"Error": {"Code": "MockException"}}, operation_name="invoke")
            self._get_boto3_method().side_effect = error
            with self.assertRaises(ErrorBotoApiCallException):
                for _ in self.lambda_invoke_executor._execute_action(given_payload):
                    pass

        @parameterized.expand(
            [
                ({}, {"InvocationType": "RequestResponse", "LogType": "Tail"}),
                ({"InvocationType": "Event"}, {"InvocationType": "Event", "LogType": "Tail"}),
                (
                    {"InvocationType": "DryRun", "Qualifier": "TestQualifier"},
                    {"InvocationType": "DryRun", "LogType": "Tail", "Qualifier": "TestQualifier"},
                ),
                (
                    {"InvocationType": "RequestResponse", "LogType": "None"},
                    {"InvocationType": "RequestResponse", "LogType": "None"},
                ),
                (
                    {"FunctionName": "MyFunction", "Payload": "{hello world}"},
                    {"InvocationType": "RequestResponse", "LogType": "Tail"},
                ),
            ]
        )
        def test_validate_action_parameters(self, parameters, expected_boto_parameters):
            self.lambda_invoke_executor.validate_action_parameters(parameters)
            self.assertEqual(self.lambda_invoke_executor.request_parameters, expected_boto_parameters)

        def test_process_log_result_with_raw_tail_log(self):
            # Traditional format: Base64-encoded string containing logs
            log_content = "START RequestId: 123\nThis is a log message\nEND RequestId: 123"
            log_result = base64.b64encode(log_content.encode("utf-8"))

            result = self.lambda_invoke_executor._process_log_result(log_result)

            self.assertIsInstance(result, RemoteInvokeLogOutput)
            self.assertEqual(result.log_output, log_content)

        def test_process_log_result_with_json_format(self):
            # New format: Base64-encoded JSON containing logGroup and logStreamName
            log_data = {
                "logGroup": "arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/my-function:*",
                "logStreamName": "2023/04/18/[$LATEST]abcdef123456",
            }
            log_result = base64.b64encode(json.dumps(log_data).encode("utf-8"))

            result = self.lambda_invoke_executor._process_log_result(log_result)

            self.assertIsInstance(result, RemoteInvokeLogOutput)
            self.assertIn("Function logs are available in CloudWatch Logs", result.log_output)
            self.assertIn(
                "Log Group: arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/my-function:*", result.log_output
            )
            self.assertIn("Log Stream: 2023/04/18/[$LATEST]abcdef123456", result.log_output)

        def test_process_log_result_with_invalid_json(self):
            # Invalid JSON but still a valid log message
            log_content = '{"This is not valid JSON but should be treated as a log'
            log_result = base64.b64encode(log_content.encode("utf-8"))

            result = self.lambda_invoke_executor._process_log_result(log_result)

            self.assertIsInstance(result, RemoteInvokeLogOutput)
            self.assertEqual(result.log_output, log_content)

        def test_process_log_result_with_json_missing_fields(self):
            # JSON without the required fields
            log_data = {"someOtherField": "value"}
            log_result = base64.b64encode(json.dumps(log_data).encode("utf-8"))

            result = self.lambda_invoke_executor._process_log_result(log_result)

            self.assertIsInstance(result, RemoteInvokeLogOutput)
            self.assertEqual(result.log_output, json.dumps(log_data))


class TestLambdaInvokeExecutor(CommonTestsLambdaInvokeExecutor.AbstractLambdaInvokeExecutorTest):
    def setUp(self) -> None:
        self.lambda_client = Mock()
        self.function_name = Mock()
        self.lambda_invoke_executor = LambdaInvokeExecutor(
            self.lambda_client, self.function_name, RemoteInvokeOutputFormat.JSON
        )

    def test_execute_action(self):
        given_payload = Mock()
        given_result = Mock()
        self.lambda_client.invoke.return_value = given_result

        result = self.lambda_invoke_executor._execute_action(given_payload)

        self.assertEqual(list(result), [RemoteInvokeResponse(given_result)])
        self.lambda_client.invoke.assert_called_with(
            FunctionName=self.function_name, Payload=given_payload, InvocationType="RequestResponse", LogType="Tail"
        )

    def test_execute_with_tenant_id(self):
        """Test that tenant_id is added to request parameters when provided"""
        given_payload = "test_payload"
        given_tenant_id = "customer-123"
        given_result = Mock()
        self.lambda_client.invoke.return_value = given_result

        # Create RemoteInvokeExecutionInfo with tenant_id
        remote_invoke_input = RemoteInvokeExecutionInfo(
            payload=given_payload,
            payload_file=None,
            tenant_id=given_tenant_id,
            durable_execution_name=None,
            parameters={},
            output_format=RemoteInvokeOutputFormat.JSON,
        )

        result = list(self.lambda_invoke_executor.execute(remote_invoke_input))

        self.assertEqual(result, [RemoteInvokeResponse(given_result)])
        self.lambda_client.invoke.assert_called_with(
            FunctionName=self.function_name,
            Payload=given_payload,
            TenantId=given_tenant_id,
            InvocationType="RequestResponse",
            LogType="Tail",
        )

    def test_execute_without_tenant_id(self):
        """Test that TenantId is not added when tenant_id is None"""
        given_payload = "test_payload"
        given_result = Mock()
        self.lambda_client.invoke.return_value = given_result

        # Create RemoteInvokeExecutionInfo without tenant_id
        remote_invoke_input = RemoteInvokeExecutionInfo(
            payload=given_payload,
            payload_file=None,
            tenant_id=None,
            durable_execution_name=None,
            parameters={},
            output_format=RemoteInvokeOutputFormat.JSON,
        )

        result = list(self.lambda_invoke_executor.execute(remote_invoke_input))

        self.assertEqual(result, [RemoteInvokeResponse(given_result)])
        self.lambda_client.invoke.assert_called_with(
            FunctionName=self.function_name,
            Payload=given_payload,
            InvocationType="RequestResponse",
            LogType="Tail",
        )

    def _get_boto3_method(self):
        return self.lambda_client.invoke


class TestLambdaInvokeWithResponseStreamExecutor(CommonTestsLambdaInvokeExecutor.AbstractLambdaInvokeExecutorTest):
    def setUp(self) -> None:
        self.lambda_client = Mock()
        self.function_name = Mock()
        self.lambda_invoke_executor = LambdaInvokeWithResponseStreamExecutor(
            self.lambda_client, self.function_name, RemoteInvokeOutputFormat.JSON
        )

    def test_execute_action(self):
        given_payload = Mock()
        given_result = Mock()
        self.lambda_client.invoke_with_response_stream.return_value = given_result

        result = self.lambda_invoke_executor._execute_action(given_payload)

        self.assertEqual(list(result), [RemoteInvokeResponse(given_result)])
        self.lambda_client.invoke_with_response_stream.assert_called_with(
            FunctionName=self.function_name, Payload=given_payload, InvocationType="RequestResponse", LogType="Tail"
        )

    def _get_boto3_method(self):
        return self.lambda_client.invoke_with_response_stream


class TestDefaultConvertToJSON(TestCase):
    def setUp(self) -> None:
        self.lambda_convert_to_default_json = DefaultConvertToJSON()
        self.output_format = RemoteInvokeOutputFormat.TEXT

    @parameterized.expand(
        [
            (None, "{}"),
            ("Hello World", '"Hello World"'),
            ('{"message": "hello world"}', '{"message": "hello world"}'),
        ]
    )
    def test_conversion(self, given_string, expected_string):
        remote_invoke_execution_info = RemoteInvokeExecutionInfo(given_string, None, None, None, {}, self.output_format)
        result = self.lambda_convert_to_default_json.map(remote_invoke_execution_info)
        self.assertEqual(result.payload, expected_string)

    def test_skip_conversion_if_file_provided(self):
        given_payload_path = "foo/bar/event.json"
        remote_invoke_execution_info = RemoteInvokeExecutionInfo(
            None, given_payload_path, None, None, {}, self.output_format
        )

        self.assertTrue(remote_invoke_execution_info.is_file_provided())
        result = self.lambda_convert_to_default_json.map(remote_invoke_execution_info)

        self.assertIsNone(result.payload)


class TestLambdaResponseConverter(TestCase):
    def setUp(self) -> None:
        self.lambda_response_converter = LambdaResponseConverter()

    def test_lambda_streaming_body_response_conversion(self):
        output_format = RemoteInvokeOutputFormat.TEXT
        given_streaming_body = Mock()
        given_decoded_string = "decoded string"
        given_streaming_body.read().decode.return_value = given_decoded_string
        given_test_result = {"Payload": given_streaming_body}
        remote_invoke_execution_info = RemoteInvokeExecutionInfo(None, None, None, None, {}, output_format)
        remote_invoke_execution_info.response = given_test_result

        expected_result = {"Payload": given_decoded_string}

        result = self.lambda_response_converter.map(remote_invoke_execution_info)

        self.assertEqual(result.response, expected_result)

    def test_lambda_streaming_body_invalid_response_exception(self):
        output_format = RemoteInvokeOutputFormat.TEXT
        given_streaming_body = Mock()
        given_decoded_string = "decoded string"
        given_streaming_body.read().decode.return_value = given_decoded_string
        given_test_result = [given_streaming_body]
        remote_invoke_execution_info = RemoteInvokeExecutionInfo(None, None, None, None, {}, output_format)
        remote_invoke_execution_info.response = given_test_result

        with self.assertRaises(InvalideBotoResponseException):
            self.lambda_response_converter.map(remote_invoke_execution_info)


class TestLambdaStreamResponseConverter(TestCase):
    def setUp(self) -> None:
        self.lambda_stream_response_converter = LambdaStreamResponseConverter()

    @parameterized.expand(
        [({LOG_RESULT: base64.b64encode(b"log output")}, {LOG_RESULT: base64.b64encode(b"log output")}), ({}, {})]
    )
    def test_lambda_streaming_body_response_conversion(self, invoke_complete_response, mapped_log_response):
        output_format = RemoteInvokeOutputFormat.TEXT
        given_test_result = {
            EVENT_STREAM: [
                {PAYLOAD_CHUNK: {PAYLOAD: b"stream1"}},
                {PAYLOAD_CHUNK: {PAYLOAD: b"stream2"}},
                {PAYLOAD_CHUNK: {PAYLOAD: b"stream3"}},
                {INVOKE_COMPLETE: invoke_complete_response},
            ]
        }
        remote_invoke_response = RemoteInvokeResponse(given_test_result)

        expected_result = {
            EVENT_STREAM: [
                {PAYLOAD_CHUNK: {PAYLOAD: "stream1"}},
                {PAYLOAD_CHUNK: {PAYLOAD: "stream2"}},
                {PAYLOAD_CHUNK: {PAYLOAD: "stream3"}},
                {INVOKE_COMPLETE: {**mapped_log_response}},
            ]
        }

        result = self.lambda_stream_response_converter.map(remote_invoke_response)
        self.assertEqual(result.response, expected_result)

    def test_lambda_streaming_body_invalid_response_exception(self):
        output_format = RemoteInvokeOutputFormat.TEXT
        remote_invoke_execution_info = RemoteInvokeExecutionInfo(None, None, None, None, {}, output_format)
        remote_invoke_execution_info.response = Mock()

        with self.assertRaises(InvalideBotoResponseException):
            self.lambda_stream_response_converter.map(remote_invoke_execution_info)


class TestLambdaInvokeExecutorUtilities(TestCase):
    @parameterized.expand(
        [
            ({}, False),
            ({"InvokeMode": "BUFFERED"}, False),
            ({"InvokeMode": "RESPONSE_STREAM"}, True),
            (ClientError({}, "operation"), False),
        ]
    )
    def test_is_function_invoke_mode_response_stream(self, boto_response, expected_result):
        given_boto_client = Mock()
        if type(boto_response) is ClientError:
            given_boto_client.get_function_url_config.side_effect = boto_response
        else:
            given_boto_client.get_function_url_config.return_value = boto_response
        self.assertEqual(_is_function_invoke_mode_response_stream(given_boto_client, "function_id"), expected_result)


class TestDurableFunctionQualifierMapper(TestCase):
    def setUp(self) -> None:
        self.mapper = DurableFunctionQualifierMapper()

    def test_adds_qualifier_when_not_present(self):
        execution_info = RemoteInvokeExecutionInfo(
            payload="test",
            payload_file=None,
            parameters={},
            tenant_id=None,
            durable_execution_name=None,
            output_format=RemoteInvokeOutputFormat.TEXT,
        )

        result = self.mapper.map(execution_info)

        self.assertEqual(result.parameters["Qualifier"], "$LATEST")

    def test_does_not_override_existing_qualifier(self):
        execution_info = RemoteInvokeExecutionInfo(
            payload="test",
            payload_file=None,
            parameters={"Qualifier": "v1"},
            tenant_id=None,
            durable_execution_name=None,
            output_format=RemoteInvokeOutputFormat.TEXT,
        )

        result = self.mapper.map(execution_info)

        self.assertEqual(result.parameters["Qualifier"], "v1")


class TestIsDurableFunction(TestCase):
    def test_is_durable_function_with_durable_config(self):
        lambda_client = Mock()
        lambda_client.get_function_configuration.return_value = {
            "FunctionName": "test-function",
            "DurableConfig": {"ExecutionTimeout": 3600, "RetentionPeriodInDays": 7},
        }

        result = _is_durable_function(lambda_client, "test-function")

        self.assertTrue(result)
        lambda_client.get_function_configuration.assert_called_once_with(FunctionName="test-function")

    def test_is_durable_function_without_durable_config(self):
        lambda_client = Mock()
        lambda_client.get_function_configuration.return_value = {
            "FunctionName": "test-function",
            "Runtime": "nodejs18.x",
        }

        result = _is_durable_function(lambda_client, "test-function")

        self.assertFalse(result)
        lambda_client.get_function_configuration.assert_called_once_with(FunctionName="test-function")

    def test_is_durable_function_with_null_durable_config(self):
        lambda_client = Mock()
        lambda_client.get_function_configuration.return_value = {
            "FunctionName": "test-function",
            "DurableConfig": None,
        }

        result = _is_durable_function(lambda_client, "test-function")

        self.assertFalse(result)
        lambda_client.get_function_configuration.assert_called_once_with(FunctionName="test-function")

    def test_is_durable_function_api_exception(self):
        lambda_client = Mock()
        lambda_client.get_function_configuration.side_effect = Exception("API Error")

        result = _is_durable_function(lambda_client, "test-function")

        self.assertFalse(result)
        lambda_client.get_function_configuration.assert_called_once_with(FunctionName="test-function")
