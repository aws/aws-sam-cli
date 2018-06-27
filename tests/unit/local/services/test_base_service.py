from unittest import TestCase
from mock import Mock, patch

from parameterized import parameterized, param

from samcli.local.services.base_service import BaseService


class TestBaseService(TestCase):

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
        lambda_runner_mock = Mock()

        service = BaseService(lambda_runner_mock, port=None, host=None, stderr=None)

        stdout = Mock()
        stdout.getvalue.return_value = stdout_data

        response, logs = service._get_lambda_output(stdout)
        self.assertEquals(logs, expected_logs)
        self.assertEquals(response, expected_response)

    @patch('samcli.local.services.base_service.Response')
    def test_service_response(self, flask_response_patch):
        flask_response_mock = Mock()

        flask_response_patch.return_value = flask_response_mock

        body = "this is the body"
        status_code = 200
        headers = {"Content-Type": "application/json"}

        actual_response = BaseService._service_response(body, headers, status_code)

        flask_response_patch.assert_called_once_with("this is the body")

        self.assertEquals(actual_response.status_code, 200)
        self.assertEquals(actual_response.headers, {"Content-Type": "application/json"})
