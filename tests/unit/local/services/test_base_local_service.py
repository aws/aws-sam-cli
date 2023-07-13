from unittest import TestCase
from unittest.mock import Mock, patch

from parameterized import parameterized, param

from samcli.local.services.base_local_service import BaseLocalService, LambdaOutputParser


class TestLocalHostRunner(TestCase):
    def test_runtime_error_raised_when_app_not_created(self):
        is_debugging = False
        service = BaseLocalService(is_debugging=is_debugging, port=3000, host="127.0.0.1")

        with self.assertRaises(RuntimeError):
            service.run()

    def test_run_starts_service_multithreaded(self):
        is_debugging = False  # multithreaded
        service = BaseLocalService(is_debugging=is_debugging, port=3000, host="127.0.0.1")

        service._app = Mock()
        app_run_mock = Mock()
        service._app.run = app_run_mock

        service.run()

        app_run_mock.assert_called_once_with(threaded=True, host="127.0.0.1", port=3000)

    def test_run_starts_service_singlethreaded(self):
        is_debugging = True  # singlethreaded
        service = BaseLocalService(is_debugging=is_debugging, port=3000, host="127.0.0.1")

        service._app = Mock()
        app_run_mock = Mock()
        service._app.run = app_run_mock

        service.run()

        app_run_mock.assert_called_once_with(threaded=False, host="127.0.0.1", port=3000)

    @patch("samcli.local.services.base_local_service.Response")
    def test_service_response(self, flask_response_patch):
        flask_response_mock = Mock()

        flask_response_patch.return_value = flask_response_mock

        body = "this is the body"
        status_code = 200
        headers = {"Content-Type": "application/json"}

        actual_response = BaseLocalService.service_response(body, headers, status_code)

        flask_response_patch.assert_called_once_with("this is the body")

        self.assertEqual(actual_response.status_code, 200)
        self.assertEqual(actual_response.headers, {"Content-Type": "application/json"})

    def test_create_returns_not_implemented(self):
        is_debugging = False
        service = BaseLocalService(is_debugging=is_debugging, port=3000, host="127.0.0.1")

        with self.assertRaises(NotImplementedError):
            service.create()


class TestLambdaOutputParser(TestCase):
    @parameterized.expand(
        [
            param("with mixed data and json response", b'data\n{"a": "b"}', 'data\n{"a": "b"}'),
            param("with response as string", b"response", "response"),
            param("with json response only", b'{"a": "b"}', '{"a": "b"}'),
            param("with one new line and json", b'\n{"a": "b"}', '\n{"a": "b"}'),
            param("with response only as string", b"this is the response line", "this is the response line"),
            param("with whitespaces", b'data\n{"a": "b"}  \n\n\n', 'data\n{"a": "b"}  \n\n\n'),
            param("with empty data", b"", ""),
            param("with just new lines", b"\n\n", "\n\n"),
            param(
                "with whitespaces",
                b"\n   \n   \n",
                "\n   \n   \n",
            ),
        ]
    )
    def test_get_lambda_output_extracts_response(self, test_case_name, stdout_data, expected_response):
        stdout = Mock()
        stdout.getvalue.return_value = stdout_data

        response, is_customer_error = LambdaOutputParser.get_lambda_output(stdout)
        self.assertEqual(response, expected_response)
        self.assertFalse(is_customer_error)

    @parameterized.expand(
        [
            param(
                '{"errorMessage": "has a message", "stackTrace": "has a stacktrace", "errorType": "has a type"}', True
            ),
            param(
                '{"errorMessage": "has a message", "stackTrace": "has a stacktrace", "errorType": "has a type",'
                '"cause": "has a cause"}',
                True,
            ),
            param('{"errorMessage": "has a message", "errorType": "has a type"}', True),
            param(
                '{"error message": "has a message", "stack Trace": "has a stacktrace", "error Type": "has a type"}',
                False,
            ),
            param(
                '{"errorMessage": "has a message", "stackTrace": "has a stacktrace", "errorType": "has a type", '
                '"hasextrakey": "value"}',
                False,
            ),
            param("notat:asdfasdf", False),
            param("errorMessage and stackTrace and errorType are in the string", False),
        ]
    )
    def test_is_lambda_error_response(self, input, exected_result):
        self.assertEqual(LambdaOutputParser.is_lambda_error_response(input), exected_result)
