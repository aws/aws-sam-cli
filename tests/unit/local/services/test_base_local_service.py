from unittest import TestCase
from mock import Mock, patch

from parameterized import parameterized, param

from samcli.local.services.base_local_service import BaseLocalService, LambdaOutputParser


class TestLocalHostRunner(TestCase):

    def test_runtime_error_raised_when_app_not_created(self):
        is_debugging = False
        service = BaseLocalService(is_debugging=is_debugging, port=3000, host='127.0.0.1')

        with self.assertRaises(RuntimeError):
            service.run()

    def test_run_starts_service_multithreaded(self):
        is_debugging = False  # multithreaded
        service = BaseLocalService(is_debugging=is_debugging, port=3000, host='127.0.0.1')

        service._app = Mock()
        app_run_mock = Mock()
        service._app.run = app_run_mock

        service.run()

        app_run_mock.assert_called_once_with(threaded=True, host='127.0.0.1', port=3000)

    def test_run_starts_service_singlethreaded(self):
        is_debugging = True  # singlethreaded
        service = BaseLocalService(is_debugging=is_debugging, port=3000, host='127.0.0.1')

        service._app = Mock()
        app_run_mock = Mock()
        service._app.run = app_run_mock

        service.run()

        app_run_mock.assert_called_once_with(threaded=False, host='127.0.0.1', port=3000)

    @patch('samcli.local.services.base_local_service.Response')
    def test_service_response(self, flask_response_patch):
        flask_response_mock = Mock()

        flask_response_patch.return_value = flask_response_mock

        body = "this is the body"
        status_code = 200
        headers = {"Content-Type": "application/json"}

        actual_response = BaseLocalService._service_response(body, headers, status_code)

        flask_response_patch.assert_called_once_with("this is the body")

        self.assertEquals(actual_response.status_code, 200)
        self.assertEquals(actual_response.headers, {"Content-Type": "application/json"})

    def test_create_returns_not_implemented(self):
        is_debugging = False
        service = BaseLocalService(is_debugging=is_debugging, port=3000, host='127.0.0.1')

        with self.assertRaises(NotImplementedError):
            service.create()


class TestLambdaOutputParser(TestCase):

    @parameterized.expand([
        param(
            "with both logs and response",
            b'this\nis\nlog\ndata\n{"a": "b"}', b'this\nis\nlog\ndata', b'{"a": "b"}'
        ),
        param(
            "with response as string",
            b"logs\nresponse", b"logs", b"response"
        ),
        param(
            "with response only",
            b'{"a": "b"}', None, b'{"a": "b"}'
        ),
        param(
            "with response only as string",
            b'this is the response line', None, b'this is the response line'
        ),
        param(
            "with whitespaces",
            b'log\ndata\n{"a": "b"}  \n\n\n', b"log\ndata", b'{"a": "b"}'
        ),
        param(
            "with empty data",
            b'', None, b''
        ),
        param(
            "with just new lines",
            b'\n\n', None, b''
        ),
        param(
            "with no data but with whitespaces",
            b'\n   \n   \n', b'\n   ', b''  # Log data with whitespaces will be in the output unchanged
        )
    ])
    def test_get_lambda_output_extracts_response(self, test_case_name, stdout_data, expected_logs, expected_response):
        stdout = Mock()
        stdout.getvalue.return_value = stdout_data

        response, logs, is_customer_error = LambdaOutputParser.get_lambda_output(stdout)
        self.assertEquals(logs, expected_logs)
        self.assertEquals(response, expected_response)
        self.assertFalse(is_customer_error)
