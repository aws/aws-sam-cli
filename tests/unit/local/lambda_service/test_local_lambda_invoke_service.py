from unittest import TestCase
from unittest.mock import Mock, patch, ANY, call

from samcli.local.lambda_service import local_lambda_invoke_service
from samcli.local.lambda_service.local_lambda_invoke_service import LocalLambdaInvokeService, FunctionNamePathConverter
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.commands.local.lib.exceptions import UnsupportedInlineCodeError


class TestLocalLambdaService(TestCase):
    def test_initalize_creates_default_values(self):
        lambda_runner_mock = Mock()
        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock, port=3001, host="127.0.0.1")
        self.assertEqual(service.port, 3001)
        self.assertEqual(service.host, "127.0.0.1")
        self.assertEqual(service.lambda_runner, lambda_runner_mock)
        self.assertIsNone(service.stderr)

    def test_initalize_with_values(self):
        lambda_runner_mock = Mock()
        stderr_mock = Mock()
        local_service = LocalLambdaInvokeService(lambda_runner_mock, port=5000, host="129.0.0.0", stderr=stderr_mock)
        self.assertEqual(local_service.port, 5000)
        self.assertEqual(local_service.host, "129.0.0.0")
        self.assertEqual(local_service.stderr, stderr_mock)
        self.assertEqual(local_service.lambda_runner, lambda_runner_mock)

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LocalLambdaInvokeService._construct_error_handling")
    @patch("samcli.local.lambda_service.local_lambda_invoke_service.Flask")
    def test_create_service_endpoints(self, flask_mock, error_handling_mock):
        app_mock = Mock()
        flask_mock.return_value = app_mock
        app_mock.url_map.converters = {}

        error_handling_mock.return_value = Mock()

        lambda_runner_mock = Mock()
        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        service.create()

        app_mock.add_url_rule.assert_called_once_with(
            "/2015-03-31/functions/<function_path:function_name>/invocations",
            endpoint="/2015-03-31/functions/<function_path:function_name>/invocations",
            view_func=service._invoke_request_handler,
            methods=["POST"],
            provide_automatic_options=False,
        )
        self.assertEqual({"function_path": FunctionNamePathConverter}, app_mock.url_map.converters)

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LocalLambdaInvokeService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LambdaOutputParser")
    def test_invoke_request_handler(self, lambda_output_parser_mock, service_response_mock):
        lambda_output_parser_mock.get_lambda_output.return_value = "hello world", False
        service_response_mock.return_value = "request response"

        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"

        local_lambda_invoke_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(response, "request response")

        lambda_runner_mock.invoke.assert_called_once_with("HelloWorld", "{}", stdout=ANY, stderr=None)
        service_response_mock.assert_called_once_with("hello world", {"Content-Type": "application/json"}, 200)

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LambdaErrorResponses")
    def test_invoke_request_handler_on_incorrect_path(self, lambda_error_responses_mock):
        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        local_lambda_invoke_service.request = request_mock

        lambda_runner_mock = Mock()
        lambda_runner_mock.invoke.side_effect = FunctionNotFound

        lambda_error_responses_mock.resource_not_found.return_value = "Couldn't find Lambda"

        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="NotFound")

        self.assertEqual(response, "Couldn't find Lambda")

        lambda_runner_mock.invoke.assert_called_once_with("NotFound", "{}", stdout=ANY, stderr=None)

        lambda_error_responses_mock.resource_not_found.assert_called_once_with("NotFound")

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LambdaErrorResponses")
    def test_invoke_request_function_contains_inline_code(self, lambda_error_responses_mock):
        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        local_lambda_invoke_service.request = request_mock

        lambda_runner_mock = Mock()
        lambda_runner_mock.invoke.side_effect = UnsupportedInlineCodeError(message="Inline code is not supported")

        lambda_error_responses_mock.not_implemented_locally.return_value = "Inline code is not supported"

        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="FunctionWithInlineCode")

        self.assertEqual(response, "Inline code is not supported")

        lambda_runner_mock.invoke.assert_called_once_with("FunctionWithInlineCode", "{}", stdout=ANY, stderr=None)

        lambda_error_responses_mock.not_implemented_locally.assert_called()

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LocalLambdaInvokeService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LambdaOutputParser")
    def test_request_handler_returns_process_stdout_when_making_response(
        self, lambda_output_parser_mock, service_response_mock
    ):
        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        local_lambda_invoke_service.request = request_mock

        lambda_response = "response"
        is_customer_error = False
        lambda_output_parser_mock.get_lambda_output.return_value = lambda_response, is_customer_error

        service_response_mock.return_value = "request response"

        lambda_runner_mock = Mock()
        stderr_mock = Mock()
        service = LocalLambdaInvokeService(
            lambda_runner=lambda_runner_mock, port=3000, host="localhost", stderr=stderr_mock
        )

        result = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(result, "request response")
        lambda_output_parser_mock.get_lambda_output.assert_called_with(ANY)

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LambdaErrorResponses")
    def test_construct_error_handling(self, lambda_error_response_mock):
        service = LocalLambdaInvokeService(lambda_runner=Mock(), port=3000, host="localhost", stderr=Mock())

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

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LocalLambdaInvokeService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LambdaOutputParser")
    def test_invoke_request_handler_with_lambda_that_errors(self, lambda_output_parser_mock, service_response_mock):
        lambda_output_parser_mock.get_lambda_output.return_value = "hello world", True
        service_response_mock.return_value = "request response"
        request_mock = Mock()
        request_mock.get_data.return_value = b"{}"
        local_lambda_invoke_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(response, "request response")

        lambda_runner_mock.invoke.assert_called_once_with("HelloWorld", "{}", stdout=ANY, stderr=None)
        service_response_mock.assert_called_once_with(
            "hello world", {"Content-Type": "application/json", "x-amz-function-error": "Unhandled"}, 200
        )

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LocalLambdaInvokeService.service_response")
    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LambdaOutputParser")
    def test_invoke_request_handler_with_no_data(self, lambda_output_parser_mock, service_response_mock):
        lambda_output_parser_mock.get_lambda_output.return_value = "hello world", False
        service_response_mock.return_value = "request response"

        request_mock = Mock()
        request_mock.get_data.return_value = None
        local_lambda_invoke_service.request = request_mock

        lambda_runner_mock = Mock()
        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock, port=3000, host="localhost")

        response = service._invoke_request_handler(function_name="HelloWorld")

        self.assertEqual(response, "request response")

        lambda_runner_mock.invoke.assert_called_once_with("HelloWorld", "{}", stdout=ANY, stderr=None)
        service_response_mock.assert_called_once_with("hello world", {"Content-Type": "application/json"}, 200)


class TestValidateRequestHandling(TestCase):
    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LambdaErrorResponses")
    def test_request_with_non_json_data(self, lambda_error_responses_mock):
        flask_request = Mock()
        flask_request.get_data.return_value = b"notat:asdfasdf"
        flask_request.headers = {}
        flask_request.content_type = "application/json"
        flask_request.args = {}
        local_lambda_invoke_service.request = flask_request

        lambda_error_responses_mock.invalid_request_content.return_value = "InvalidRequestContent"

        response = LocalLambdaInvokeService.validate_request()

        self.assertEqual(response, "InvalidRequestContent")

        expected_called_with = "Could not parse request body into json: No JSON object could be decoded"

        lambda_error_responses_mock.invalid_request_content.assert_called_once_with(expected_called_with)

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LambdaErrorResponses")
    def test_request_with_query_strings(self, lambda_error_responses_mock):
        flask_request = Mock()
        flask_request.get_data.return_value = None
        flask_request.headers = {}
        flask_request.content_type = "application/json"
        flask_request.args = {"key": "value"}
        local_lambda_invoke_service.request = flask_request

        lambda_error_responses_mock.invalid_request_content.return_value = "InvalidRequestContent"

        response = LocalLambdaInvokeService.validate_request()

        self.assertEqual(response, "InvalidRequestContent")

        lambda_error_responses_mock.invalid_request_content.assert_called_once_with(
            "Query Parameters are not supported"
        )

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LambdaErrorResponses")
    def test_request_log_type_not_None(self, lambda_error_responses_mock):
        flask_request = Mock()
        flask_request.get_data.return_value = None
        flask_request.headers = {"X-Amz-Log-Type": "Tail"}
        flask_request.content_type = "application/json"
        flask_request.args = {}
        local_lambda_invoke_service.request = flask_request

        lambda_error_responses_mock.not_implemented_locally.return_value = "NotImplementedLocally"

        response = LocalLambdaInvokeService.validate_request()

        self.assertEqual(response, "NotImplementedLocally")

        lambda_error_responses_mock.not_implemented_locally.assert_called_once_with(
            "log-type: Tail is not supported. None is only supported."
        )

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.LambdaErrorResponses")
    def test_request_invocation_type_not_ResponseRequest(self, lambda_error_responses_mock):
        flask_request = Mock()
        flask_request.get_data.return_value = None
        flask_request.headers = {"X-Amz-Invocation-Type": "DryRun"}
        flask_request.content_type = "application/json"
        flask_request.args = {}
        local_lambda_invoke_service.request = flask_request

        lambda_error_responses_mock.not_implemented_locally.return_value = "NotImplementedLocally"

        response = LocalLambdaInvokeService.validate_request()

        self.assertEqual(response, "NotImplementedLocally")

        lambda_error_responses_mock.not_implemented_locally.assert_called_once_with(
            "invocation-type: DryRun is not supported. RequestResponse is only supported."
        )

    @patch("samcli.local.lambda_service.local_lambda_invoke_service.request")
    def test_request_with_no_data(self, flask_request):
        flask_request.get_data.return_value = None
        flask_request.headers = {}
        flask_request.content_type = "application/json"
        flask_request.args = {}
        local_lambda_invoke_service.request = flask_request

        response = LocalLambdaInvokeService.validate_request()

        self.assertIsNone(response)


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
