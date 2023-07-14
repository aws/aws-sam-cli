from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized, parameterized_class
from samcli.lib.remote_invoke.stepfunctions_invoke_executors import (
    SfnDescribeExecutionResponseConverter,
    RemoteInvokeOutputFormat,
    InvalideBotoResponseException,
    StepFunctionsStartExecutionExecutor,
    ParamValidationError,
    InvalidResourceBotoParameterException,
    ErrorBotoApiCallException,
    ClientError,
    RemoteInvokeLogOutput,
)
from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeExecutionInfo, RemoteInvokeResponse
from datetime import datetime


@parameterized_class(
    "output",
    [[RemoteInvokeOutputFormat.TEXT], [RemoteInvokeOutputFormat.JSON]],
)
class TestStepFunctionsStartExecutionExecutor(TestCase):
    output: RemoteInvokeOutputFormat

    def setUp(self) -> None:
        self.stepfunctions_client = Mock()
        self.state_machine_arn = Mock()
        self.stepfunctions_invoke_executor = StepFunctionsStartExecutionExecutor(
            self.stepfunctions_client, self.state_machine_arn, self.output
        )

    @patch("samcli.lib.remote_invoke.stepfunctions_invoke_executors.time")
    def test_execute_action_successful(self, patched_time):
        patched_time.sleep = Mock()
        mock_exec_name = "mock_execution_name"
        mock_exec_arn = "MockArn"
        given_input = '{"input_key": "value"}'
        mock_response = {
            "executionArn": mock_exec_arn,
            "status": "SUCCEEDED",
            "output": '{"output_key": "mock_output"}',
        }
        self.stepfunctions_client.start_execution.return_value = {"executionArn": mock_exec_arn}
        self.stepfunctions_client.describe_execution.side_effect = [
            {"executionArn": mock_exec_arn, "status": "RUNNING"},
            mock_response,
        ]
        self.stepfunctions_invoke_executor.validate_action_parameters({"name": mock_exec_name})
        result = self.stepfunctions_invoke_executor._execute_action(given_input)

        if self.output == RemoteInvokeOutputFormat.JSON:
            self.assertEqual(list(result), [RemoteInvokeResponse(mock_response)])
        else:
            self.assertEqual(list(result), [RemoteInvokeResponse(mock_response["output"])])

        self.stepfunctions_client.start_execution.assert_called_with(
            stateMachineArn=self.state_machine_arn, input=given_input, name=mock_exec_name
        )
        self.stepfunctions_client.describe_execution.assert_called()

    @patch("samcli.lib.remote_invoke.stepfunctions_invoke_executors.time")
    def test_execute_action_not_successful(self, patched_time):
        patched_time.sleep = Mock()
        mock_exec_name = "mock_execution_name"
        mock_exec_arn = "MockArn"
        mock_error = "MockError"
        mock_cause = "Execution failed due to mock error"
        given_input = '{"input_key": "value"}'
        mock_response = {"executionArn": mock_exec_arn, "status": "FAILED", "error": mock_error, "cause": mock_cause}
        self.stepfunctions_client.start_execution.return_value = {"executionArn": mock_exec_arn}
        self.stepfunctions_client.describe_execution.side_effect = [
            {"executionArn": mock_exec_arn, "status": "RUNNING"},
            mock_response,
        ]
        self.stepfunctions_invoke_executor.validate_action_parameters({"name": mock_exec_name})
        result = self.stepfunctions_invoke_executor._execute_action(given_input)

        expected_response = f"The execution failed due to the error: {mock_error} and cause: {mock_cause}"
        if self.output == RemoteInvokeOutputFormat.JSON:
            self.assertEqual(list(result), [RemoteInvokeResponse(mock_response)])
        else:
            self.assertEqual(list(result), [RemoteInvokeLogOutput(expected_response)])

    @parameterized.expand(
        [
            ({}, {"name": "sam_remote_invoke_20230710T072625"}),
            ({"name": "custom_execution_name"}, {"name": "custom_execution_name"}),
            (
                {"traceHeader": "Mock X-Ray trace header"},
                {"traceHeader": "Mock X-Ray trace header", "name": "sam_remote_invoke_20230710T072625"},
            ),
            (
                {"stateMachineArn": "ParameterProvidedArn", "input": "ParameterProvidedInput"},
                {"name": "sam_remote_invoke_20230710T072625"},
            ),
            (
                {"invalidParameterKey": "invalidParameterValue"},
                {"invalidParameterKey": "invalidParameterValue", "name": "sam_remote_invoke_20230710T072625"},
            ),
        ]
    )
    @patch("samcli.lib.remote_invoke.stepfunctions_invoke_executors.datetime")
    def test_validate_action_parameters(self, parameters, expected_boto_parameters, patched_datetime):
        patched_datetime.now.return_value = datetime(2023, 7, 10, 7, 26, 25)
        self.stepfunctions_invoke_executor.validate_action_parameters(parameters)
        self.assertEqual(self.stepfunctions_invoke_executor.request_parameters, expected_boto_parameters)

    def test_execute_action_invalid_parameter_key_throws_parameter_validation_exception(self):
        given_input = "input"
        error = ParamValidationError(report="Invalid parameters")
        self.stepfunctions_client.start_execution.side_effect = error
        with self.assertRaises(InvalidResourceBotoParameterException):
            self.stepfunctions_invoke_executor.validate_action_parameters({})
            for _ in self.stepfunctions_invoke_executor._execute_action(given_input):
                pass

    def test_execute_action_throws_client_error_exception(self):
        given_input = "input"
        error = ClientError(error_response={"Error": {"Code": "MockException"}}, operation_name="invoke")
        self.stepfunctions_client.start_execution.side_effect = error
        with self.assertRaises(ErrorBotoApiCallException):
            self.stepfunctions_invoke_executor.validate_action_parameters({})
            for _ in self.stepfunctions_invoke_executor._execute_action(given_input):
                pass


class TestSfnDescribeExecutionResponseConverter(TestCase):
    def setUp(self) -> None:
        self.sfn_response_converter = SfnDescribeExecutionResponseConverter()

    def test_stepfunctions_response_conversion(self):
        output_format = RemoteInvokeOutputFormat.JSON
        given_output_string = "output string"
        execution_date = datetime(2022, 12, 25, 00, 00, 00)
        given_execution_result = {
            "output": given_output_string,
            "startDate": execution_date,
            "stopDate": execution_date,
        }
        remote_invoke_execution_info = RemoteInvokeExecutionInfo(None, None, {}, output_format)
        remote_invoke_execution_info.response = given_execution_result

        expected_result = {
            "output": given_output_string,
            "startDate": "2022-12-25 00:00:00.000000",
            "stopDate": "2022-12-25 00:00:00.000000",
        }

        result = self.sfn_response_converter.map(remote_invoke_execution_info)

        self.assertEqual(result.response, expected_result)

    def test_stepfunctions_invalid_response_exception(self):
        output_format = RemoteInvokeOutputFormat.JSON
        given_output_response = Mock()
        given_output_string = "output string"
        given_output_response.read().decode.return_value = given_output_string
        given_test_result = [given_output_response]
        remote_invoke_execution_info = RemoteInvokeExecutionInfo(None, None, {}, output_format)
        remote_invoke_execution_info.response = given_test_result

        with self.assertRaises(InvalideBotoResponseException):
            self.sfn_response_converter.map(remote_invoke_execution_info)
