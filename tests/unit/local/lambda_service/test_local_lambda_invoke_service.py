from unittest import TestCase
from mock import Mock, patch, ANY

from samcli.local.lambda_service.local_lambda_invoke_service import LocalLambdaInvokeService
from samcli.local.lambdafn.exceptions import FunctionNotFound


class TestLocalLambdaService(TestCase):

    def test_initalize_creates_default_values(self):
        lambda_runner_mock = Mock()
        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock, port=3001, host='127.0.0.1')
        self.assertEquals(service.port, 3001)
        self.assertEquals(service.host, '127.0.0.1')
        self.assertEquals(service.lambda_runner, lambda_runner_mock)
        self.assertIsNone(service.stderr)

    def test_initalize_with_values(self):
        lambda_runner_mock = Mock()
        stderr_mock = Mock()
        local_service = LocalLambdaInvokeService(lambda_runner_mock, port=5000, host='129.0.0.0', stderr=stderr_mock)
        self.assertEquals(local_service.port, 5000)
        self.assertEquals(local_service.host, '129.0.0.0')
        self.assertEquals(local_service.stderr, stderr_mock)
        self.assertEquals(local_service.lambda_runner, lambda_runner_mock)

    @patch('samcli.local.lambda_service.local_lambda_invoke_service.LocalLambdaInvokeService._construct_error_handling')
    @patch('samcli.local.lambda_service.local_lambda_invoke_service.Flask')
    def test_create_service_endpoints(self, flask_mock, error_handling_mock):
        app_mock = Mock()
        flask_mock.return_value = app_mock

        error_handling_mock.return_value = Mock()

        lambda_runner_mock = Mock()
        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock, port=3000, host='localhost')

        service.create()

        app_mock.add_url_rule.assert_called_once_with('/2015-03-31/functions/<function_name>/invocations',
                                                      endpoint='/2015-03-31/functions/<function_name>/invocations',
                                                      view_func=service._invoke_request_handler,
                                                      methods=['POST'],
                                                      provide_automatic_options=False)

    @patch('samcli.local.lambda_service.local_lambda_invoke_service.LocalLambdaInvokeService._service_response')
    @patch('samcli.local.lambda_service.local_lambda_invoke_service.LambdaOutputParser')
    @patch('samcli.local.lambda_service.local_lambda_invoke_service.request')
    def test_invoke_request_handler(self, request_mock, lambda_output_parser_mock, service_response_mock):
        lambda_output_parser_mock.get_lambda_output.return_value = 'hello world', None
        service_response_mock.return_value = 'request response'
        request_mock.get_data.return_value = b'{}'

        lambda_runner_mock = Mock()
        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock, port=3000, host='localhost')

        response = service._invoke_request_handler(function_name='HelloWorld')

        self.assertEquals(response, 'request response')

        lambda_runner_mock.invoke.assert_called_once_with('HelloWorld', '{}', stdout=ANY, stderr=None)
        service_response_mock.assert_called_once_with('hello world', {'Content-Type': 'application/json'}, 200)

    @patch('samcli.local.lambda_service.local_lambda_invoke_service.request')
    def test_invoke_request_handler_on_incorrect_path(self, request_mock):
        request_mock.get_data.return_value = b'{}'
        lambda_runner_mock = Mock()
        lambda_runner_mock.invoke.side_effect = FunctionNotFound
        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock, port=3000, host='localhost')

        with self.assertRaises(Exception):
            service._invoke_request_handler(function_name='NotFound')

        lambda_runner_mock.invoke.assert_called_once_with('NotFound', '{}', stdout=ANY, stderr=None)

    @patch('samcli.local.lambda_service.local_lambda_invoke_service.LocalLambdaInvokeService._service_response')
    @patch('samcli.local.lambda_service.local_lambda_invoke_service.LambdaOutputParser')
    @patch('samcli.local.lambda_service.local_lambda_invoke_service.request')
    def test_request_handler_returns_process_stdout_when_making_response(self, request_mock, lambda_output_parser_mock,
                                                                         service_response_mock):
        request_mock.get_data.return_value = b'{}'

        lambda_logs = "logs"
        lambda_response = "response"
        lambda_output_parser_mock.get_lambda_output.return_value = lambda_response, lambda_logs

        service_response_mock.return_value = 'request response'

        lambda_runner_mock = Mock()
        stderr_mock = Mock()
        service = LocalLambdaInvokeService(lambda_runner=lambda_runner_mock,
                                           port=3000,
                                           host='localhost',
                                           stderr=stderr_mock)

        result = service._invoke_request_handler(function_name='HelloWorld')

        self.assertEquals(result, 'request response')
        lambda_output_parser_mock.get_lambda_output.assert_called_with(ANY)

        # Make sure the logs are written to stderr
        stderr_mock.write.assert_called_with(lambda_logs)
