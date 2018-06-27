from unittest import TestCase
from mock import Mock, patch, ANY

from samcli.local.lambda_service.service import LocalLambdaService
from samcli.local.lambdafn.exceptions import FunctionNotFound


class TestLocalLambdaService(TestCase):

    def test_initalize_creates_default_values(self):
        lambda_runner_mock = Mock()
        service = LocalLambdaService(function_name_list=['HelloWorld'], lambda_runner=lambda_runner_mock)
        self.assertEquals(service.port, 3001)
        self.assertEquals(service.host, '127.0.0.1')
        self.assertEquals(service.function_name_list, ['HelloWorld'])
        self.assertEquals(service.lambda_runner, lambda_runner_mock)
        self.assertIsNone(service.stderr)

    def test_initalize_with_values(self):
        lambda_runner_mock = Mock()
        stderr_mock = Mock()
        local_service = LocalLambdaService([], lambda_runner_mock, port=5000, host='129.0.0.0', stderr=stderr_mock)
        self.assertEquals(local_service.port, 5000)
        self.assertEquals(local_service.host, '129.0.0.0')
        self.assertEquals(local_service.function_name_list, [])
        self.assertEquals(local_service.stderr, stderr_mock)
        self.assertEquals(local_service.lambda_runner, lambda_runner_mock)

    @patch('samcli.local.lambda_service.service.LocalLambdaService._construct_error_handling')
    @patch('samcli.local.lambda_service.service.Flask')
    def test_create_service_endpoints(self, flask_mock, error_handling_mock):
        app_mock = Mock()
        flask_mock.return_value = app_mock

        error_handling_mock.return_value = Mock()

        lambda_runner_mock = Mock()
        service = LocalLambdaService(function_name_list=['HelloWorld'], lambda_runner=lambda_runner_mock)

        service.create()

        app_mock.add_url_rule.assert_called_once_with('/2015-03-31/functions/HelloWorld/invocations',
                                                      endpoint='/2015-03-31/functions/HelloWorld/invocations',
                                                      view_func=service._invoke_request_handler,
                                                      methods=['POST'],
                                                      provide_automatic_options=False)

    def test_runtime_error_raised_when_app_not_created(self):
        lambda_runner_mock = Mock()
        service = LocalLambdaService(function_name_list=['HelloWorld'], lambda_runner=lambda_runner_mock)

        with self.assertRaises(RuntimeError):
            service.run()

    def test_run_starts_service_multithreaded(self):
        lambda_runner_mock = Mock()
        service = LocalLambdaService(function_name_list=['HelloWorld'], lambda_runner=lambda_runner_mock)

        service._app = Mock()
        app_run_mock = Mock()
        service._app.run = app_run_mock

        lambda_runner_mock.is_debugging.return_value = False  # multithreaded
        service.run()

        app_run_mock.assert_called_once_with(threaded=True, host='127.0.0.1', port=3001)

    def test_run_starts_service_singlethreaded(self):
        lambda_runner_mock = Mock()
        service = LocalLambdaService(function_name_list=['HelloWorld'], lambda_runner=lambda_runner_mock)

        service._app = Mock()
        app_run_mock = Mock()
        service._app.run = app_run_mock

        lambda_runner_mock.is_debugging.return_value = True  # single threaded
        service.run()

        app_run_mock.assert_called_once_with(threaded=False, host='127.0.0.1', port=3001)

    @patch('samcli.local.lambda_service.service.LocalLambdaService._service_response')
    @patch('samcli.local.lambda_service.service.LocalLambdaService._get_lambda_output')
    @patch('samcli.local.lambda_service.service.request')
    def test_invoke_request_handler(self, request_mock, get_lambda_output_mock, service_response_mock):
        request_mock.path = '/2015-03-31/functions/HelloWorld/invocations'
        get_lambda_output_mock.return_value = 'hello world', None
        service_response_mock.return_value = 'request response'

        lambda_runner_mock = Mock()
        service = LocalLambdaService(function_name_list=['HelloWorld'], lambda_runner=lambda_runner_mock)

        response = service._invoke_request_handler()

        self.assertEquals(response, 'request response')

        lambda_runner_mock.invoke.assert_called_once_with('HelloWorld', {}, stdout=ANY, stderr=None)
        service_response_mock.assert_called_once_with('hello world', {'Content-Type': 'application/json'}, 200)

    @patch('samcli.local.lambda_service.service.request')
    def test_invoke_request_handler_on_incorrect_path(self, request_mock):
        # This will not match the regex
        request_mock.path = '/2015-03-31/functions/'

        lambda_runner_mock = Mock()
        lambda_runner_mock.invoke.side_effect = FunctionNotFound
        service = LocalLambdaService(function_name_list=['HelloWorld'], lambda_runner=lambda_runner_mock)

        with self.assertRaises(Exception):
            service._invoke_request_handler()

        lambda_runner_mock.invoke.assert_called_once_with('', {}, stdout=ANY, stderr=None)

    @patch('samcli.local.lambda_service.service.LocalLambdaService._service_response')
    @patch('samcli.local.lambda_service.service.LocalLambdaService._get_lambda_output')
    @patch('samcli.local.lambda_service.service.request')
    def test_request_handler_returns_process_stdout_when_making_response(self, request_mock, get_lambda_output_mock,
                                                                         service_response_mock):
        request_mock.path = '/2015-03-31/functions/HelloWorld/invocations'

        lambda_logs = "logs"
        lambda_response = "response"
        get_lambda_output_mock.return_value = lambda_response, lambda_logs

        service_response_mock.return_value = 'request response'

        lambda_runner_mock = Mock()
        stderr_mock = Mock()
        service = LocalLambdaService(function_name_list=['HelloWorld'],
                                     lambda_runner=lambda_runner_mock,
                                     stderr=stderr_mock)

        result = service._invoke_request_handler()

        self.assertEquals(result, 'request response')
        service._get_lambda_output.assert_called_with(ANY)

        # Make sure the logs are written to stderr
        stderr_mock.write.assert_called_with(lambda_logs)
