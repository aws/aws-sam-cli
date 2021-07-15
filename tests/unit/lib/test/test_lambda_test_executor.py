from unittest import TestCase
from unittest.mock import Mock

from samcli.lib.test.lambda_test_executor import (
    LambdaInvokeExecutor,
    LambdaConvertToDefaultJSON,
    LambdaResponseConverter,
)
from samcli.lib.test.test_executors import TestExecutionInfo


class TestLambdaInvokeExecutor(TestCase):
    def setUp(self) -> None:
        self.lambda_client = Mock()
        self.function_name = Mock()
        self.lambda_invoke_executor = LambdaInvokeExecutor(self.lambda_client, self.function_name)

    def test_execute_action(self):
        given_payload = Mock()
        given_result = Mock()
        self.lambda_client.invoke.return_value = given_result

        result = self.lambda_invoke_executor._execute_action(given_payload)

        self.assertEqual(result, given_result)
        self.lambda_client.invoke.assert_called_with(FunctionName=self.function_name, Payload=given_payload)


class TestLambdaConvertToDefaultJSON(TestCase):
    def setUp(self) -> None:
        self.lambda_convert_to_default_json = LambdaConvertToDefaultJSON()

    def test_conversion(self):
        given_string = "Hello World"
        test_execution_info = TestExecutionInfo(given_string, None)

        expected_string = '"Hello World"'

        result = self.lambda_convert_to_default_json.map(test_execution_info)

        self.assertEqual(result.payload, expected_string)

    def test_skip(self):
        given_string = '{"body": "Hello World"}'
        test_execution_info = TestExecutionInfo(given_string, None)

        result = self.lambda_convert_to_default_json.map(test_execution_info)

        self.assertEqual(result.payload, given_string)


class TestLambdaResponseConverter(TestCase):
    def setUp(self) -> None:
        self.lambda_response_converter = LambdaResponseConverter()

    def test_conversion(self):
        given_streaming_body = Mock()
        given_decoded_string = "decoded string"
        given_streaming_body.read().decode.return_value = given_decoded_string
        given_test_result = {"Payload": given_streaming_body}
        test_execution_info = TestExecutionInfo(None, None)
        test_execution_info.response = given_test_result

        expected_result = {"Payload": given_decoded_string}

        result = self.lambda_response_converter.map(test_execution_info)

        self.assertEqual(result.response, expected_result)
