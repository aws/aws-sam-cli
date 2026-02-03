import threading
import json
from datetime import datetime
from unittest import TestCase
from unittest.mock import ANY, Mock, call, patch

from parameterized import parameterized

from samcli.commands.local.lib.exceptions import UnsupportedInlineCodeError
from samcli.lib.utils.name_utils import InvalidFunctionNameException
from samcli.local.docker.exceptions import DockerContainerCreationFailedException
from samcli.local.lambda_service import local_lambda_http_service
from samcli.local.lambda_service.local_lambda_http_service import (
    DateTimeEncoder,
    FunctionNamePathConverter,
    LocalLambdaHttpService,
)
from samcli.local.lambdafn.exceptions import DurableExecutionNotFound, FunctionNotFound


class TestLocalLambdaHttpService(TestCase):
    def test_initalize_creates_default_values(self):
        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3001, host="127.0.0.1")
        self.assertEqual(service.port, 3001)
        self.assertEqual(service.host, "127.0.0.1")
        self.assertEqual(service.lambda_runner, lambda_runner_mock)
        self.assertIsNone(service.stderr)

    def test_initalize_with_values(self):
        lambda_runner_mock = Mock()
        stderr_mock = Mock()
        local_service = LocalLambdaHttpService(lambda_runner_mock, port=5000, host="129.0.0.0", stderr=stderr_mock)
        self.assertEqual(local_service.port, 5000)
        self.assertEqual(local_service.host, "129.0.0.0")
        self.assertEqual(local_service.stderr, stderr_mock)
        self.assertEqual(local_service.lambda_runner, lambda_runner_mock)

    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService._construct_error_handling")
    @patch("samcli.local.lambda_service.local_lambda_http_service.Flask")
    def test_create_service_endpoints(self, flask_mock, error_handling_mock):
        app_mock = Mock()
        flask_mock.return_value = app_mock
        app_mock.url_map.converters = {}

        error_handling_mock.return_value = Mock()

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        service.create()

        # Should be called 7 times: 1 for Lambda invocations + 6 for durable functions APIs
        self.assertEqual(app_mock.add_url_rule.call_count, 7)

        # Verify the Lambda invocation endpoint was added
        app_mock.add_url_rule.assert_any_call(
            "/2015-03-31/functions/<function_path:function_name>/invocations",
            endpoint="/2015-03-31/functions/<function_path:function_name>/invocations",
            view_func=service._invoke_request_handler,
            methods=["POST"],
            provide_automatic_options=False,
        )

        # Verify durable functions endpoints were added
        app_mock.add_url_rule.assert_any_call(
            "/2025-12-01/durable-executions/<durable_execution_arn>",
            endpoint="get_durable_execution",
            view_func=service._get_durable_execution_handler,
            methods=["GET"],
        )

        app_mock.add_url_rule.assert_any_call(
            "/2025-12-01/durable-executions/<durable_execution_arn>/history",
            endpoint="get_durable_execution_history",
            view_func=service._get_durable_execution_history_handler,
            methods=["GET"],
        )

        app_mock.add_url_rule.assert_any_call(
            "/2025-12-01/durable-executions/<durable_execution_arn>/stop",
            endpoint="stop_durable_execution",
            view_func=service._stop_durable_execution_handler,
            methods=["POST"],
        )

        app_mock.add_url_rule.assert_any_call(
            "/2025-12-01/durable-execution-callbacks/<callback_id>/succeed",
            endpoint="send_callback_success",
            view_func=service._send_callback_success_handler,
            methods=["POST"],
        )

        app_mock.add_url_rule.assert_any_call(
            "/2025-12-01/durable-execution-callbacks/<callback_id>/fail",
            endpoint="send_callback_failure",
            view_func=service._send_callback_failure_handler,
            methods=["POST"],
        )

        app_mock.add_url_rule.assert_any_call(
            "/2025-12-01/durable-execution-callbacks/<callback_id>/heartbeat",
            endpoint="send_callback_heartbeat",
            view_func=service._send_callback_heartbeat_handler,
            methods=["POST"],
        )

        self.assertEqual({"function_path": FunctionNamePathConverter}, app_mock.url_map.converters)

    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaOutputParser")
    def test_invoke_request_handler(self, lambda_output_parser_mock, service_response_mock):
        lambda_output_parser_mock.get_lambda_output.return_value = "hello world", False
        service_response_mock.return_value = "request response"

        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {}

        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(response, "request response")

        lambda_runner_mock.invoke.assert_called_once_with(
            "HelloWorld",
            "{}",
            invocation_type="RequestResponse",
            durable_execution_name=None,
            tenant_id=None,
            stdout=ANY,
            stderr=None,
            function=ANY,
        )
        service_response_mock.assert_called_once_with("hello world", {"Content-Type": "application/json"}, 200)

    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaOutputParser")
    def test_invoke_request_handler_with_durable_execution_name_header(
        self, lambda_output_parser_mock, service_response_mock
    ):
        lambda_output_parser_mock.get_lambda_output.return_value = "hello world", False
        service_response_mock.return_value = "request response"

        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {"X-Amz-Durable-Execution-Name": "test-execution-name"}

        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(response, "request response")

        lambda_runner_mock.invoke.assert_called_once_with(
            "HelloWorld",
            "{}",
            invocation_type="RequestResponse",
            durable_execution_name="test-execution-name",
            tenant_id=None,
            stdout=ANY,
            stderr=None,
            function=ANY,
        )
        service_response_mock.assert_called_once_with("hello world", {"Content-Type": "application/json"}, 200)

    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaOutputParser")
    def test_invoke_request_handler_with_durable_execution_arn(self, lambda_output_parser_mock, service_response_mock):
        lambda_output_parser_mock.get_lambda_output.return_value = "hello world", False
        service_response_mock.return_value = "request response"

        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        expected_arn = (
            "arn:aws:lambda:us-east-1:123456789012:function:HelloWorld:$LATEST/"
            "durable-execution/test-execution-name/test-execution-id"
        )
        lambda_runner_mock.invoke.return_value = {"X-Amz-Durable-Execution-Arn": expected_arn}

        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(response, "request response")
        lambda_runner_mock.invoke.assert_called_once_with(
            "HelloWorld",
            "{}",
            invocation_type="RequestResponse",
            durable_execution_name=None,
            tenant_id=None,
            stdout=ANY,
            stderr=None,
            function=ANY,
        )
        service_response_mock.assert_called_once_with(
            "hello world", {"Content-Type": "application/json", "X-Amz-Durable-Execution-Arn": expected_arn}, 200
        )

    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_invoke_request_handler_on_incorrect_path(self, lambda_error_responses_mock):
        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        lambda_runner_mock.get_function.side_effect = FunctionNotFound

        lambda_error_responses_mock.resource_not_found.return_value = "Couldn't find Lambda"

        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="NotFound")

        self.assertEqual(response, "Couldn't find Lambda")

        # get_function is called first; invoke is never called when it raises
        lambda_runner_mock.get_function.assert_called_once_with("NotFound", None)
        lambda_runner_mock.invoke.assert_not_called()

        lambda_error_responses_mock.resource_not_found.assert_called_once_with("NotFound")

    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_invoke_request_function_contains_inline_code(self, lambda_error_responses_mock):
        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        lambda_runner_mock.get_function.side_effect = UnsupportedInlineCodeError(message="Inline code is not supported")

        lambda_error_responses_mock.not_implemented_locally.return_value = "Inline code is not supported"

        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="FunctionWithInlineCode")

        self.assertEqual(response, "Inline code is not supported")

        lambda_runner_mock.get_function.assert_called_once_with("FunctionWithInlineCode", None)
        lambda_runner_mock.invoke.assert_not_called()
        lambda_error_responses_mock.not_implemented_locally.assert_called()

    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_invoke_request_container_creation_failed(self, lambda_error_responses_mock):
        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        lambda_runner_mock.invoke.side_effect = DockerContainerCreationFailedException("container creation failed")

        lambda_error_responses_mock.container_creation_failed.return_value = "Container creation failed"

        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="FunctionContainerCreationFailed")

        self.assertEqual(response, "Container creation failed")

        lambda_runner_mock.invoke.assert_called_once_with(
            "FunctionContainerCreationFailed",
            "{}",
            invocation_type="RequestResponse",
            durable_execution_name=None,
            tenant_id=None,
            stdout=ANY,
            stderr=None,
            function=ANY,
        )

        lambda_error_responses_mock.container_creation_failed.assert_called()

    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaOutputParser")
    def test_request_handler_returns_process_stdout_when_making_response(
        self, lambda_output_parser_mock, service_response_mock
    ):
        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {}
        local_lambda_http_service.request = request_mock

        lambda_response = "response"
        is_customer_error = False
        lambda_output_parser_mock.get_lambda_output.return_value = lambda_response, is_customer_error

        service_response_mock.return_value = "request response"

        lambda_runner_mock = Mock()
        stderr_mock = Mock()
        service = LocalLambdaHttpService(
            lambda_runner=lambda_runner_mock, port=3000, host="localhost", stderr=stderr_mock
        )

        result = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(result, "request response")
        lambda_output_parser_mock.get_lambda_output.assert_called_with(ANY, ANY)

    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_construct_error_handling(self, lambda_error_response_mock):
        service = LocalLambdaHttpService(lambda_runner=Mock(), port=3000, host="localhost", stderr=Mock())

        flask_app_mock = Mock()
        service._app = flask_app_mock
        service._construct_error_handling()

        flask_app_mock.register_error_handler.assert_has_calls(
            [
                call(500, lambda_error_response_mock.generic_service_exception),
                call(404, lambda_error_response_mock.generic_path_not_found),
                call(405, lambda_error_response_mock.generic_method_not_allowed),
            ]
        )

    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaOutputParser")
    def test_invoke_request_handler_with_lambda_that_errors(self, lambda_output_parser_mock, service_response_mock):
        lambda_output_parser_mock.get_lambda_output.return_value = "hello world", True
        service_response_mock.return_value = "request response"
        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(response, "request response")

        lambda_runner_mock.invoke.assert_called_once_with(
            "HelloWorld",
            "{}",
            invocation_type="RequestResponse",
            durable_execution_name=None,
            tenant_id=None,
            stdout=ANY,
            stderr=None,
            function=ANY,
        )
        service_response_mock.assert_called_once_with(
            "hello world", {"Content-Type": "application/json", "x-amz-function-error": "Unhandled"}, 200
        )

    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaOutputParser")
    def test_invoke_request_handler_with_no_data(self, lambda_output_parser_mock, service_response_mock):
        lambda_output_parser_mock.get_lambda_output.return_value = "hello world", False
        service_response_mock.return_value = "request response"

        request_mock = Mock()
        request_mock.get_data.return_value = None
        request_mock.args = {}
        request_mock.headers = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(response, "request response")

        lambda_runner_mock.invoke.assert_called_once_with(
            "HelloWorld",
            "{}",
            invocation_type="RequestResponse",
            durable_execution_name=None,
            tenant_id=None,
            stdout=ANY,
            stderr=None,
            function=ANY,
        )
        service_response_mock.assert_called_once_with("hello world", {"Content-Type": "application/json"}, 200)

    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaOutputParser")
    def test_invoke_request_handler_async_invocation_returns_202(
        self, lambda_output_parser_mock, service_response_mock
    ):
        # Test that async invocation (Event type) returns 202 status code with empty body
        lambda_output_parser_mock.get_lambda_output.return_value = "execution started", False
        service_response_mock.return_value = "request response"

        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {"X-Amz-Invocation-Type": "Event"}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        lambda_runner_mock.invoke.return_value = {
            "X-Amz-Durable-Execution-Arn": "arn:aws:lambda:us-west-2:123456789012:function:test-function:$LATEST/durable-execution/test-123"
        }
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(response, "request response")
        lambda_runner_mock.invoke.assert_called_once_with(
            "HelloWorld",
            "{}",
            invocation_type="Event",
            durable_execution_name=None,
            tenant_id=None,
            stdout=ANY,
            stderr=None,
            function=ANY,
        )
        # For async invocation, should return empty body with 202 status and execution ARN header
        service_response_mock.assert_called_once_with(
            "",
            {
                "Content-Type": "application/json",
            },
            202,
        )

    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_invoke_request_handler_async_invocation_unsupported_function_returns_error(
        self, lambda_error_responses_mock
    ):
        # Test that async invocation on non-durable function throws UnsupportedInvocationType error
        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {"X-Amz-Invocation-Type": "DryRun"}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        from samcli.local.lambdafn.exceptions import UnsupportedInvocationType

        lambda_runner_mock.invoke.side_effect = UnsupportedInvocationType("Dry Run invocation not supported")

        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        lambda_error_responses_mock.not_implemented_locally.return_value = "error response"

        result = service._invoke_request_handler(function_name="HelloWorld")

        lambda_runner_mock.invoke.assert_called_once_with(
            "HelloWorld",
            "{}",
            invocation_type="DryRun",
            durable_execution_name=None,
            tenant_id=None,
            stdout=ANY,
            stderr=None,
            function=ANY,
        )
        lambda_error_responses_mock.not_implemented_locally.assert_called_once_with("Dry Run invocation not supported")
        self.assertEqual(result, "error response")

    def test_event_invocation_runs_async_task(self):
        # Test that Event invocation type runs the function asynchronously
        handler_returned = threading.Event()
        finished = threading.Event()

        def fake_invoke(*args, **kwargs):
            if handler_returned.wait(timeout=5):
                finished.set()

        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {"X-Amz-Invocation-Type": "Event"}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")
        service._invoke_lambda = fake_invoke
        service.create()

        response = service._invoke_request_handler(function_name="HelloWorld")

        # Assert that first a 202 response is returned
        self.assertEqual(response.status_code, 202)

        # Then assert that invoke has not finished
        self.assertFalse(finished.is_set())
        handler_returned.set()

        # Finally assert that invoke has finished
        self.assertTrue(finished.wait(timeout=5), "Task never finished")

    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_http_service.ThreadPoolExecutor")
    def test_invoke_request_handler_async_invocation_submits_to_executor(
        self, executor_class_mock, service_response_mock
    ):
        # Test that async invocation (Event type) submits _invoke_async_lambda to executor
        service_response_mock.return_value = "request response"
        executor_mock = Mock()
        executor_class_mock.return_value = executor_mock
        future_mock = Mock()
        executor_mock.submit.return_value = future_mock

        request_mock = Mock()
        request_mock.get_data.return_value = b'{"test": "data"}'
        request_mock.args = {}
        request_mock.headers = {"X-Amz-Invocation-Type": "Event"}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(response, "request response")
        # Verify executor.submit was called with _invoke_async_lambda and correct arguments
        executor_mock.submit.assert_called_once()
        submit_call = executor_mock.submit.call_args
        self.assertEqual(submit_call[0][0], service._invoke_async_lambda)
        self.assertEqual(submit_call[1]["function_name"], "HelloWorld")
        self.assertEqual(submit_call[1]["request_data"], '{"test": "data"}')
        self.assertEqual(submit_call[1]["invocation_type"], "Event")
        # Verify 202 response is returned
        service_response_mock.assert_called_once_with("", {"Content-Type": "application/json"}, 202)

    @patch("samcli.local.lambda_service.local_lambda_http_service.LOG")
    @patch("samcli.local.lambda_service.local_lambda_http_service.ThreadPoolExecutor")
    def test_invoke_async_lambda_logs_exceptions(self, executor_class_mock, log_mock):
        # Test that exceptions in async lambda invocation are logged
        executor_mock = Mock()
        executor_class_mock.return_value = executor_mock

        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {"X-Amz-Invocation-Type": "Event"}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        test_exception = Exception("Test async exception")
        lambda_runner_mock.invoke.side_effect = test_exception

        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        # Trigger async invocation
        service._invoke_request_handler(function_name="HelloWorld")

        # Get the submitted function and execute it to trigger exception
        submit_call = executor_mock.submit.call_args
        async_function = submit_call[0][0]
        async_kwargs = submit_call[1]

        # Execute the async function which should catch and log the exception
        async_function(**async_kwargs)

        # Verify exception was logged
        log_mock.error.assert_called_once()
        error_call = log_mock.error.call_args
        # Check format string
        self.assertEqual(error_call[0][0], "Async invocation failed for function %s: %s")
        # Check function name argument
        self.assertEqual(error_call[0][1], "HelloWorld")
        # Check exception message argument
        self.assertEqual(error_call[0][2], "Test async exception")
        # Check exc_info keyword argument
        self.assertTrue(error_call[1]["exc_info"])

    @patch("samcli.local.lambda_service.local_lambda_http_service.ThreadPoolExecutor")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_invoke_request_handler_async_invocation_function_not_found_returns_error(
        self, lambda_error_responses_mock, executor_class_mock
    ):
        # Test that async invocation (Event type) returns error when function doesn't exist
        executor_mock = Mock()
        executor_class_mock.return_value = executor_mock

        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {"X-Amz-Invocation-Type": "Event"}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        lambda_runner_mock.get_function.side_effect = FunctionNotFound
        lambda_error_responses_mock.resource_not_found.return_value = "function not found response"

        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="NonExistentFunction")

        # Verify error response is returned
        self.assertEqual(response, "function not found response")
        # Verify get_function was called to validate
        lambda_runner_mock.get_function.assert_called_once_with("NonExistentFunction", None)
        # Verify executor was NOT called since validation failed
        executor_mock.submit.assert_not_called()
        # Verify error response uses normalized function name
        lambda_error_responses_mock.resource_not_found.assert_called_once_with("NonExistentFunction")

    @patch("samcli.local.lambda_service.local_lambda_http_service.LOG")
    @patch("samcli.local.lambda_service.local_lambda_http_service.ThreadPoolExecutor")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_invoke_request_handler_async_invocation_invalid_function_name_returns_error(
        self, lambda_error_responses_mock, executor_class_mock, log_mock
    ):
        # Test that async invocation (Event type) returns error when function name is invalid
        executor_mock = Mock()
        executor_class_mock.return_value = executor_mock

        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {"X-Amz-Invocation-Type": "Event"}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        test_exception = InvalidFunctionNameException("Invalid function name format")
        lambda_runner_mock.get_function.side_effect = test_exception
        lambda_error_responses_mock.validation_exception.return_value = "validation error response"

        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="Invalid@Function#Name")

        # Verify error response is returned
        self.assertEqual(response, "validation error response")
        # Verify get_function was called to validate
        lambda_runner_mock.get_function.assert_called_once_with("Invalid@Function#Name", None)
        # Verify executor was NOT called since validation failed
        executor_mock.submit.assert_not_called()
        # Verify error was logged
        log_mock.error.assert_called_once_with("Validation error: %s", "Invalid function name format")
        # Verify validation exception was called with the error message
        lambda_error_responses_mock.validation_exception.assert_called_once_with("Invalid function name format")


class TestValidateInvokeRequestHandling(TestCase):
    def setUp(self):
        self.service = LocalLambdaHttpService(lambda_runner=Mock(), port=3000, host="localhost")

    def _setup_request_mock(self, request_mock, **overrides):
        """Helper method to set up request mock with defaults and overrides"""
        request_mock.endpoint = self.service.INVOKE_ENDPOINT
        request_mock.get_data.return_value = None
        request_mock.headers = {}
        request_mock.content_type = "application/json"
        request_mock.args = {}

        # Apply any overrides
        for key, value in overrides.items():
            setattr(request_mock, key, value)

    @patch("samcli.local.lambda_service.local_lambda_http_service.request")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_invoke_request_with_non_json_data(self, lambda_error_responses_mock, request_mock):
        self._setup_request_mock(request_mock, get_data=Mock(return_value=b"notat:asdfasdf"))

        lambda_error_responses_mock.invalid_request_content.return_value = "InvalidRequestContent"

        response = LocalLambdaHttpService.validate_request()

        self.assertEqual(response, "InvalidRequestContent")

        expected_called_with = "Could not parse request body into json: No JSON object could be decoded"

        lambda_error_responses_mock.invalid_request_content.assert_called_once_with(expected_called_with)

    @patch("samcli.local.lambda_service.local_lambda_http_service.request")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_invoke_request_with_query_strings(self, lambda_error_responses_mock, request_mock):
        self._setup_request_mock(request_mock, args={"key": "value"})

        lambda_error_responses_mock.invalid_request_content.return_value = "InvalidRequestContent"

        response = LocalLambdaHttpService.validate_request()

        self.assertEqual(response, "InvalidRequestContent")

        lambda_error_responses_mock.invalid_request_content.assert_called_once_with(
            "Query Parameters are not supported"
        )

    @patch("samcli.local.lambda_service.local_lambda_http_service.request")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_invoke_request_log_type_not_None(self, lambda_error_responses_mock, request_mock):
        self._setup_request_mock(request_mock, headers={"X-Amz-Log-Type": "Tail"})

        lambda_error_responses_mock.not_implemented_locally.return_value = "NotImplementedLocally"

        response = LocalLambdaHttpService.validate_request()

        self.assertEqual(response, "NotImplementedLocally")

        lambda_error_responses_mock.not_implemented_locally.assert_called_once_with(
            "log-type: Tail is not supported. None is only supported."
        )

    @patch("samcli.local.lambda_service.local_lambda_http_service.request")
    def test_invoke_request_with_no_data(self, request_mock):
        self._setup_request_mock(request_mock)  # Uses all defaults

        response = LocalLambdaHttpService.validate_request()

        self.assertIsNone(response)

    @patch("samcli.local.lambda_service.local_lambda_http_service.request")
    def test_non_invoke_endpoint_not_validated(self, request_mock):
        self._setup_request_mock(request_mock, endpoint="/some/other/endpoint")

        response = LocalLambdaHttpService.validate_request()

        self.assertIsNone(response)

    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_invoke_request_handler_invalid_function_name(self, error_responses_mock):
        # Setup mocks - get_function is called first and raises InvalidFunctionNameException
        error_responses_mock.validation_exception.return_value = "validation exception response"

        request_mock = Mock()
        request_mock.get_data.return_value = b'{"test": "data"}'
        request_mock.args = {}
        request_mock.headers = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        lambda_runner_mock.get_function.side_effect = InvalidFunctionNameException("Invalid function name")
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler("invalid-function-name")

        self.assertEqual(response, "validation exception response")
        lambda_runner_mock.get_function.assert_called_once_with("invalid-function-name", None)
        error_responses_mock.validation_exception.assert_called_once_with("Invalid function name")


class TestPathConverter(TestCase):
    def test_path_converter_to_url_accepts_function_full_path(self):
        map = Mock()
        map.charset = "utf-8"
        path_converter = FunctionNamePathConverter(map)
        full_path = "parent_stack/function_id"
        output = path_converter.to_url(full_path)
        self.assertEqual(full_path, output)

    def test_path_converter_to_python_accepts_function_full_path(self):
        map = Mock()
        map.charset = "utf-8"
        path_converter = FunctionNamePathConverter(map)
        full_path = "parent_stack/function_id"
        output = path_converter.to_python(full_path)
        self.assertEqual(full_path, output)

    def test_path_converter_matches_function_full_path(self):
        map = Mock()
        map.charset = "utf-8"
        path_converter = FunctionNamePathConverter(map)
        full_path = "parent_stack/function_id"
        self.assertRegex(full_path, path_converter.regex)

    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaOutputParser")
    def test_invoke_request_handler_with_arn(self, lambda_output_parser_mock, service_response_mock):
        """Test that invoke request handler correctly normalizes ARN to function name"""
        lambda_output_parser_mock.get_lambda_output.return_value = "hello world", False
        service_response_mock.return_value = "request response"

        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        # Call with ARN instead of function name
        arn = "arn:aws:lambda:us-east-1:123456789012:function:HelloWorld"
        response = service._invoke_request_handler(function_name=arn)

        self.assertEqual(response, "request response")

        # Verify that the lambda runner was called with the normalized function name
        lambda_runner_mock.invoke.assert_called_once_with(
            "HelloWorld",
            "{}",
            invocation_type="RequestResponse",
            durable_execution_name=None,
            tenant_id=None,
            stdout=ANY,
            stderr=None,
            function=ANY,
        )
        service_response_mock.assert_called_once_with("hello world", {"Content-Type": "application/json"}, 200)

    @patch("samcli.local.lambda_service.local_lambda_http_service.normalize_sam_function_identifier")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_invoke_request_handler_function_not_found_with_arn(self, lambda_error_responses_mock, normalize_mock):
        """Test that error handling uses normalized function name when ARN is provided"""
        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        lambda_runner_mock.get_function.side_effect = FunctionNotFound
        normalize_mock.return_value = "NotFound"

        lambda_error_responses_mock.resource_not_found.return_value = "Couldn't find Lambda"

        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        # Call with ARN instead of function name
        arn = "arn:aws:lambda:us-east-1:123456789012:function:NotFound"
        response = service._invoke_request_handler(function_name=arn)

        self.assertEqual(response, "Couldn't find Lambda")

        # get_function is called first with the ARN; invoke is never called when it raises
        lambda_runner_mock.get_function.assert_called_once_with(arn, None)
        lambda_runner_mock.invoke.assert_not_called()

        # Verify that error response uses the normalized function name
        lambda_error_responses_mock.resource_not_found.assert_called_once_with("NotFound")


class TestDurableExecutionHandlers(TestCase):
    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    def test_get_durable_execution_handler_success(self, service_response_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.get_durable_execution.return_value = {"DurableExecutionArn": "test-arn", "Status": "RUNNING"}
        service_response_mock.return_value = "success response"

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._get_durable_execution_handler("test-arn")

        self.assertEqual(response, "success response")
        context_class_mock.assert_called_once()
        client_mock.get_durable_execution.assert_called_once_with("test-arn")

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_get_durable_execution_handler_not_found(self, error_responses_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.get_durable_execution.side_effect = DurableExecutionNotFound("Not found")
        error_responses_mock.durable_execution_not_found.return_value = "not found response"

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._get_durable_execution_handler("test-arn")

        self.assertEqual(response, "not found response")
        error_responses_mock.durable_execution_not_found.assert_called_once_with("test-arn")

    @parameterized.expand(
        [
            ("false", False),
            ("true", True),
        ]
    )
    @patch("samcli.local.lambda_service.local_lambda_http_service.request")
    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    def test_get_durable_execution_history_handler_with_include_execution_data(
        self,
        query_param_value,
        expected_include_execution_data,
        service_response_mock,
        context_class_mock,
        request_mock,
    ):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.get_durable_execution_history.return_value = {"Events": [], "NextMarker": None}
        service_response_mock.return_value = "success response"
        request_mock.args.get.return_value = query_param_value

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._get_durable_execution_history_handler("test-arn")

        self.assertEqual(response, "success response")
        context_class_mock.assert_called_once()
        client_mock.get_durable_execution_history.assert_called_once_with(
            "test-arn", include_execution_data=expected_include_execution_data
        )
        request_mock.args.get.assert_called_once_with("IncludeExecutionData", "false")

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_get_durable_execution_history_handler_not_found(self, error_responses_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.get_durable_execution_history.side_effect = DurableExecutionNotFound("Not found")
        error_responses_mock.durable_execution_not_found.return_value = "not found response"

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._get_durable_execution_history_handler("test-arn")

        self.assertEqual(response, "not found response")
        error_responses_mock.durable_execution_not_found.assert_called_once_with("test-arn")

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    def test_get_durable_execution_handler_url_decoding(self, service_response_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.get_durable_execution.return_value = {"DurableExecutionArn": "decoded-arn", "Status": "RUNNING"}
        service_response_mock.return_value = "success response"

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        # Test with URL-encoded ARN
        encoded_arn = "arn%3Aaws%3Alambda%3Aus-west-2%3A123456789012%3Afunction%3Atest"
        service._get_durable_execution_handler(encoded_arn)

        # Should decode the ARN before passing to client
        expected_decoded = "arn:aws:lambda:us-west-2:123456789012:function:test"
        client_mock.get_durable_execution.assert_called_once_with(expected_decoded)

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    def test_stop_durable_execution_handler_success(self, service_response_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.stop_durable_execution.return_value = {}
        service_response_mock.return_value = "success response"

        request_mock = Mock()
        request_mock.get_json.return_value = {"Error": "test error"}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._stop_durable_execution_handler("test-arn")

        self.assertEqual(response, "success response")
        context_class_mock.assert_called_once()
        client_mock.stop_durable_execution.assert_called_once_with(
            durable_execution_arn="test-arn",
            error="test error",
        )

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_stop_durable_execution_handler_not_found(self, error_responses_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.stop_durable_execution.side_effect = DurableExecutionNotFound("Not found")
        error_responses_mock.durable_execution_not_found.return_value = "not found response"

        request_mock = Mock()
        request_mock.get_json.return_value = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._stop_durable_execution_handler("test-arn")

        self.assertEqual(response, "not found response")
        error_responses_mock.durable_execution_not_found.assert_called_once_with("test-arn")

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    def test_stop_durable_execution_handler_empty_payload(self, service_response_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.stop_durable_execution.return_value = {"StopDate": "2025-11-04T17:56:00Z"}
        service_response_mock.return_value = "success response"

        request_mock = Mock()
        request_mock.get_json.return_value = None  # Empty payload
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._stop_durable_execution_handler("test-arn")

        self.assertEqual(response, "success response")
        context_class_mock.assert_called_once()
        client_mock.stop_durable_execution.assert_called_once_with(
            durable_execution_arn="test-arn",
            error=None,  # Should be None when no payload
        )

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    def test_stop_durable_execution_handler_url_decoding(self, service_response_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.stop_durable_execution.return_value = {"StopDate": "2025-11-04T17:56:00Z"}
        service_response_mock.return_value = "success response"

        request_mock = Mock()
        request_mock.get_json.return_value = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        # Test with URL-encoded ARN
        encoded_arn = "arn%3Aaws%3Alambda%3Aus-west-2%3A123456789012%3Afunction%3Atest"
        response = service._stop_durable_execution_handler(encoded_arn)

        # Should decode the ARN before passing to client
        expected_decoded = "arn:aws:lambda:us-west-2:123456789012:function:test"
        client_mock.stop_durable_execution.assert_called_once_with(
            durable_execution_arn=expected_decoded,
            error=None,
        )
        self.assertEqual(response, "success response")

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_stop_durable_execution_handler_exception(self, error_responses_mock, context_class_mock):
        # Setup mocks to raise exception
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.stop_durable_execution.side_effect = Exception("Test exception")
        error_responses_mock.generic_service_exception.return_value = "service exception response"

        request_mock = Mock()
        request_mock.get_json.return_value = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._stop_durable_execution_handler("test-arn")

        self.assertEqual(response, "service exception response")
        error_responses_mock.generic_service_exception.assert_called_once()

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    def test_send_callback_success_handler_success(self, service_response_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.send_callback_success.return_value = {}
        service_response_mock.return_value = "success response"

        request_mock = Mock()
        request_mock.get_json.return_value = {"Result": "test result"}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._send_callback_success_handler("test-callback-id")

        self.assertEqual(response, "success response")
        context_class_mock.assert_called_once()
        client_mock.send_callback_success.assert_called_once_with(
            callback_id="test-callback-id",
            result="test result",
        )

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    def test_send_callback_success_handler_empty_payload(self, service_response_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.send_callback_success.return_value = {}
        service_response_mock.return_value = "success response"

        request_mock = Mock()
        request_mock.get_json.return_value = None  # Simulate empty payload
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._send_callback_success_handler("test-callback-id")

        self.assertEqual(response, "success response")
        context_class_mock.assert_called_once()
        client_mock.send_callback_success.assert_called_once_with(
            callback_id="test-callback-id",
            result=None,  # Should be None when no payload
        )

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_send_callback_success_handler_exception(self, error_responses_mock, context_class_mock):
        # Setup mocks to raise exception
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.send_callback_success.side_effect = Exception("Test exception")
        error_responses_mock.generic_service_exception.return_value = "service exception response"

        request_mock = Mock()
        request_mock.get_json.return_value = {"Result": "test"}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._send_callback_success_handler("test-callback-id")

        self.assertEqual(response, "service exception response")
        error_responses_mock.generic_service_exception.assert_called_once()

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    def test_send_callback_failure_handler_success(self, service_response_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.send_callback_failure.return_value = {}
        service_response_mock.return_value = "success response"

        request_mock = Mock()
        request_mock.get_json.return_value = {
            "ErrorData": "test error",
            "ErrorType": "TestError",
            "ErrorMessage": "Test error message",
        }
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._send_callback_failure_handler("test-callback-id")

        self.assertEqual(response, "success response")
        context_class_mock.assert_called_once()
        client_mock.send_callback_failure.assert_called_once_with(
            callback_id="test-callback-id",
            error_data="test error",
            stack_trace=None,
            error_type="TestError",
            error_message="Test error message",
        )

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_send_callback_failure_handler_exception(self, error_responses_mock, context_class_mock):
        # Setup mocks to raise exception
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.send_callback_failure.side_effect = Exception("Test exception")
        error_responses_mock.generic_service_exception.return_value = "service exception response"

        request_mock = Mock()
        request_mock.get_json.return_value = {"ErrorData": "test"}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._send_callback_failure_handler("test-callback-id")

        self.assertEqual(response, "service exception response")
        error_responses_mock.generic_service_exception.assert_called_once()

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    def test_send_callback_heartbeat_handler_success(self, service_response_mock, context_class_mock):
        # Setup mocks
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.send_callback_heartbeat.return_value = {}
        service_response_mock.return_value = "success response"

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._send_callback_heartbeat_handler("test-callback-id")

        self.assertEqual(response, "success response")
        context_class_mock.assert_called_once()
        client_mock.send_callback_heartbeat.assert_called_once_with(callback_id="test-callback-id")

    @patch("samcli.local.lambda_service.local_lambda_http_service.DurableContext")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaErrorResponses")
    def test_send_callback_heartbeat_handler_exception(self, error_responses_mock, context_class_mock):
        # Setup mocks to raise exception
        context_mock = Mock()
        client_mock = Mock()
        context_class_mock.return_value.__enter__.return_value = context_mock
        context_mock.client = client_mock
        client_mock.send_callback_heartbeat.side_effect = Exception("Test exception")
        error_responses_mock.generic_service_exception.return_value = "service exception response"

        lambda_runner_mock = Mock()
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._send_callback_heartbeat_handler("test-callback-id")

        self.assertEqual(response, "service exception response")
        error_responses_mock.generic_service_exception.assert_called_once()


class TestDurableExecutionHeaderCombination(TestCase):
    @patch("samcli.local.lambda_service.local_lambda_http_service.LocalLambdaHttpService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_http_service.LambdaOutputParser")
    def test_invoke_request_handler_combines_headers_with_durable_execution_arn(
        self, lambda_output_parser_mock, service_response_mock
    ):
        lambda_output_parser_mock.get_lambda_output.return_value = "hello world", False
        service_response_mock.return_value = "request response"

        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        request_mock.args = {}
        request_mock.headers = {}
        local_lambda_http_service.request = request_mock

        lambda_runner_mock = Mock()
        lambda_runner_mock.invoke.return_value = {
            "X-Amz-Durable-Execution-Arn": (
                "arn:aws:lambda:us-west-2:123456789012:function:test-function:$LATEST/durable-execution/test-123"
            )
        }
        service = LocalLambdaHttpService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(response, "request response")
        lambda_runner_mock.invoke.assert_called_once_with(
            "HelloWorld",
            "{}",
            invocation_type="RequestResponse",
            durable_execution_name=None,
            tenant_id=None,
            stdout=ANY,
            stderr=None,
            function=ANY,
        )
        expected_headers = {
            "Content-Type": "application/json",
            "X-Amz-Durable-Execution-Arn": (
                "arn:aws:lambda:us-west-2:123456789012:function:test-function:$LATEST/durable-execution/test-123"
            ),
        }
        service_response_mock.assert_called_once_with("hello world", expected_headers, 200)
