import base64
from datetime import datetime
from time import time
from typing import Any
from unittest import TestCase
from unittest.mock import Mock
from parameterized import parameterized_class

from samcli.local.apigw.event_constructor import (
    _event_headers,
    _event_http_headers,
    _query_string_params,
    _query_string_params_v_2_0,
    construct_v1_event,
    construct_v2_event_http,
)
from samcli.local.apigw.local_apigw_service import LocalApigwService


input_scenarios = [
    # No Data
    (None, None, [], None, False),
    # Standard text formats
    ("application/json", b'{"key": "value"}', [], '{"key": "value"}', False),
    ("text/plain", b"Hello, world!", [], "Hello, world!", False),
    ("text/html", b"<html><body>Hello</body></html>", [], "<html><body>Hello</body></html>", False),
    ("application/xml", b"<root><item>value</item></root>", [], "<root><item>value</item></root>", False),
    # Binary formats with matching binary_types
    (
        "image/gif",
        b"\x47\x49\x46\x38\x39\x61 binary data",
        ["image/gif"],
        base64.b64encode(b"\x47\x49\x46\x38\x39\x61 binary data").decode("ascii"),
        True,
    ),
    (
        "image/png",
        b"\x89PNG\r\n\x1a\n binary data",
        ["image/png"],
        base64.b64encode(b"\x89PNG\r\n\x1a\n binary data").decode("ascii"),
        True,
    ),
    (
        "image/jpeg",
        b"\xff\xd8\xff\xe0 binary data",
        ["image/jpeg"],
        base64.b64encode(b"\xff\xd8\xff\xe0 binary data").decode("ascii"),
        True,
    ),
    (
        "application/pdf",
        b"%PDF-1.5 binary data",
        ["application/pdf"],
        base64.b64encode(b"%PDF-1.5 binary data").decode("ascii"),
        True,
    ),
    (
        "application/octet-stream",
        b"\x00\x01\x02\x03 binary data",
        ["application/octet-stream"],
        base64.b64encode(b"\x00\x01\x02\x03 binary data").decode("ascii"),
        True,
    ),
    # Binary format without matching binary_type (should be treated as text)
    # This might fail UTF-8 decoding and fall back to base64, so we need to handle both cases
    (
        "image/png",
        b"\x89PNG\r\n\x1a\n binary data",
        [],
        base64.b64encode(b"\x89PNG\r\n\x1a\n binary data").decode("ascii"),
        True,
    ),
    # Text format with invalid UTF-8 (should fall back to base64)
    ("text/plain", b"\xff\xfe invalid utf-8", [], base64.b64encode(b"\xff\xfe invalid utf-8").decode("ascii"), True),
    # Multipart form data (should always be base64 encoded)
    (
        "multipart/form-data",
        b'--boundary\r\nContent-Disposition: form-data; name="file"\r\n\r\nbinary data\r\n--boundary--',
        [],
        base64.b64encode(
            b'--boundary\r\nContent-Disposition: form-data; name="file"\r\n\r\nbinary data\r\n--boundary--'
        ).decode("ascii"),
        True,
    ),
    # Special cases
    (
        None,
        b"some binary data",
        ["*/*"],
        base64.b64encode(b"some binary data").decode("utf-8"),
        True,
    ),  # No MIME type but */* in binary_types
    ("application/json", None, [], None, False),  # No data
    (
        "application/x-www-form-urlencoded",
        b"param1=value1&param2=value2",
        [],
        "param1=value1&param2=value2",
        False,
    ),  # Form data
    # Edge cases
    ("text/csv", b"id,name\n1,test", ["text/csv"], base64.b64encode(b"id,name\n1,test").decode("ascii"), True),
    (
        "application/zip",
        b"PK\x03\x04 zip data",
        ["*/*"],
        base64.b64encode(b"PK\x03\x04 zip data").decode("ascii"),
        True,
    ),
    ("application/javascript", b"function test() { return true; }", [], "function test() { return true; }", False),
]


@parameterized_class(
    ("request_mimetype", "request_get_data_return", "binary_types", "expected_body", "expected_is_base64"),
    input_scenarios,
)
class TestService_construct_event(TestCase):
    request_mimetype: str
    request_get_data_return: bytes
    binary_types: list
    expected_body: Any
    expected_is_base64: bool

    def setUp(self):
        self.request_mock = Mock()
        self.request_mock.endpoint = "endpoint"
        self.request_mock.path = "path"
        self.request_mock.method = "GET"
        self.request_mock.remote_addr = "190.0.0.0"
        self.request_mock.host = "190.0.0.1"
        self.request_mock.get_data.return_value = self.request_get_data_return
        self.request_mock.mimetype = self.request_mimetype
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"query": ["params"]}.items()
        self.request_mock.args = query_param_args_mock
        headers_mock = Mock()
        headers_mock.keys.return_value = ["Content-Type", "X-Test"]
        headers_mock.get.side_effect = ["application/json", "Value"]
        headers_mock.getlist.side_effect = [["application/json"], ["Value"]]
        self.request_mock.headers = headers_mock
        self.request_mock.view_args = {"path": "params"}
        self.request_mock.scheme = "http"
        environ_dict = {"SERVER_PROTOCOL": "HTTP/1.1"}
        self.request_mock.environ = environ_dict

        self.expected_dict = {
            "body": self.expected_body,
            "httpMethod": "GET",
            "multiValueQueryStringParameters": {"query": ["params"]},
            "queryStringParameters": {"query": "params"},
            "resource": "endpoint",
            "requestContext": {
                "httpMethod": "GET",
                "requestId": "c6af9ac6-7b61-11e6-9a41-93e8deadbeef",
                "path": "endpoint",
                "extendedRequestId": None,
                "resourceId": "123456",
                "apiId": "1234567890",
                "stage": None,
                "resourcePath": "endpoint",
                "identity": {
                    "accountId": None,
                    "apiKey": None,
                    "userArn": None,
                    "cognitoAuthenticationProvider": None,
                    "cognitoIdentityPoolId": None,
                    "userAgent": "Custom User Agent String",
                    "caller": None,
                    "cognitoAuthenticationType": None,
                    "sourceIp": "190.0.0.0",
                    "user": None,
                },
                "accountId": "123456789012",
                "domainName": "190.0.0.1",
                "protocol": "HTTP/1.1",
            },
            "headers": {
                "Content-Type": "application/json",
                "X-Test": "Value",
                "X-Forwarded-Port": "3000",
                "X-Forwarded-Proto": "http",
            },
            "multiValueHeaders": {
                "Content-Type": ["application/json"],
                "X-Test": ["Value"],
                "X-Forwarded-Port": ["3000"],
                "X-Forwarded-Proto": ["http"],
            },
            "stageVariables": None,
            "path": "path",
            "pathParameters": {"path": "params"},
            "isBase64Encoded": self.expected_is_base64,
        }

    def test_construct_event(self):
        actual_event = construct_v1_event(self.request_mock, 3000, self.binary_types)
        self.maxDiff = None

        # Remove dynamic fields from requestContext
        request_id = actual_event["requestContext"].pop("requestId", None)
        request_time = actual_event["requestContext"].pop("requestTime", None)
        request_time_epoch = actual_event["requestContext"].pop("requestTimeEpoch", None)

        self.assertEqual(len(request_id), 36)
        self.assertIsInstance(request_time, str)

        parsed_request_time = datetime.strptime(request_time, "%d/%b/%Y:%H:%M:%S +0000")
        self.assertIsInstance(parsed_request_time, datetime)

        self.assertIsInstance(request_time_epoch, int)

        self.expected_dict["requestContext"].pop("requestId", None)
        self.expected_dict["requestContext"].pop("requestTime", None)
        self.expected_dict["requestContext"].pop("requestTimeEpoch", None)

        self.assertEqual(actual_event, self.expected_dict)

    def test_event_headers_with_empty_list(self):
        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = []
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        actual_query_string = _event_headers(request_mock, "3000")
        self.assertEqual(
            actual_query_string,
            (
                {"X-Forwarded-Proto": "http", "X-Forwarded-Port": "3000"},
                {"X-Forwarded-Proto": ["http"], "X-Forwarded-Port": ["3000"]},
            ),
        )

    def test_event_headers_with_non_empty_list(self):
        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = ["Content-Type", "X-Test"]
        headers_mock.get.side_effect = ["application/json", "Value"]
        headers_mock.getlist.side_effect = [["application/json"], ["Value"]]
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        actual_query_string = _event_headers(request_mock, "3000")
        self.assertEqual(
            actual_query_string,
            (
                {
                    "Content-Type": "application/json",
                    "X-Test": "Value",
                    "X-Forwarded-Proto": "http",
                    "X-Forwarded-Port": "3000",
                },
                {
                    "Content-Type": ["application/json"],
                    "X-Test": ["Value"],
                    "X-Forwarded-Proto": ["http"],
                    "X-Forwarded-Port": ["3000"],
                },
            ),
        )

    def test_query_string_params_with_empty_params(self):
        request_mock = Mock()
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {}.items()
        request_mock.args = query_param_args_mock

        actual_query_string = _query_string_params(request_mock)
        self.assertEqual(actual_query_string, ({}, {}))

    def test_query_string_params_with_param_value_being_empty_list(self):
        request_mock = Mock()
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"param": []}.items()
        request_mock.args = query_param_args_mock

        actual_query_string = _query_string_params(request_mock)
        self.assertEqual(actual_query_string, ({"param": ""}, {"param": [""]}))

    def test_query_string_params_with_param_value_being_non_empty_list(self):
        request_mock = Mock()
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"param": ["a", "b"]}.items()
        request_mock.args = query_param_args_mock

        actual_query_string = _query_string_params(request_mock)
        self.assertEqual(actual_query_string, ({"param": "b"}, {"param": ["a", "b"]}))

    def test_query_string_params_v_2_0_with_param_value_being_non_empty_list(self):
        request_mock = Mock()
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"param": ["a", "b"]}.items()
        request_mock.args = query_param_args_mock

        actual_query_string = _query_string_params_v_2_0(request_mock)
        self.assertEqual(actual_query_string, {"param": "a,b"})


@parameterized_class(
    ("request_mimetype", "request_get_data_return", "binary_types", "expected_body", "expected_is_base64"),
    input_scenarios,
)
class TestService_construct_event_http(TestCase):
    request_mimetype: str
    request_get_data_return: bytes
    binary_types: list
    expected_body: Any
    expected_is_base64: bool

    def setUp(self):
        self.request_mock = Mock()
        self.request_mock.endpoint = "endpoint"
        self.request_mock.method = "GET"
        self.request_mock.path = "/endpoint"
        self.request_mock.get_data.return_value = self.request_get_data_return
        self.request_mock.mimetype = self.request_mimetype
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"query": ["param1", "param2"]}.items()
        self.request_mock.args = query_param_args_mock
        self.request_mock.query_string = b"query=params"
        headers_mock = Mock()
        headers_mock.keys.return_value = ["Content-Type", "X-Test"]
        headers_mock.get.side_effect = ["application/json", "Value"]
        headers_mock.getlist.side_effect = [["application/json"], ["Value"]]
        self.request_mock.headers = headers_mock
        self.request_mock.remote_addr = "190.0.0.0"
        self.request_mock.view_args = {"path": "params"}
        self.request_mock.scheme = "http"
        cookies_mock = Mock()
        cookies_mock.keys.return_value = ["cookie1", "cookie2"]
        cookies_mock.get.side_effect = ["test", "test"]
        self.request_mock.cookies = cookies_mock
        self.request_time_epoch = int(time())
        self.request_time = datetime.utcnow().strftime("%d/%b/%Y:%H:%M:%S +0000")

        self.expected_dict = {
            "version": "2.0",
            "routeKey": "GET /endpoint",
            "rawPath": "/endpoint",
            "rawQueryString": "query=params",
            "cookies": ["cookie1=test", "cookie2=test"],
            "headers": {
                "Content-Type": "application/json",
                "X-Test": "Value",
                "X-Forwarded-Proto": "http",
                "X-Forwarded-Port": "3000",
            },
            "queryStringParameters": {"query": "param1,param2"},
            "requestContext": {
                "accountId": "123456789012",
                "apiId": "1234567890",
                "domainName": "localhost",
                "domainPrefix": "localhost",
                "http": {
                    "method": "GET",
                    "path": "/endpoint",
                    "protocol": "HTTP/1.1",
                    "sourceIp": "190.0.0.0",
                    "userAgent": "Custom User Agent String",
                },
                "requestId": "",
                "routeKey": "GET /endpoint",
                "stage": "$default",
                "time": self.request_time,
                "timeEpoch": self.request_time_epoch,
            },
            "body": self.expected_body,
            "pathParameters": {"path": "params"},
            "stageVariables": None,
            "isBase64Encoded": self.expected_is_base64,
        }

    def test_construct_event_with_data(self):
        actual_event = construct_v2_event_http(
            self.request_mock,
            3000,
            binary_types=self.binary_types,
            route_key="GET /endpoint",
            request_time_epoch=self.request_time_epoch,
            request_time=self.request_time,
        )
        self.maxDiff = None

        # Remove dynamic fields from requestContext
        request_id = actual_event["requestContext"].pop("requestId", None)
        request_time = actual_event["requestContext"].pop("time", None)
        request_time_epoch = actual_event["requestContext"].pop("timeEpoch", None)

        self.assertEqual(len(request_id), 36)
        self.assertIsInstance(request_time, str)

        parsed_request_time = datetime.strptime(request_time, "%d/%b/%Y:%H:%M:%S +0000")
        self.assertIsInstance(parsed_request_time, datetime)

        self.assertIsInstance(request_time_epoch, int)

        self.expected_dict["requestContext"].pop("requestId", None)
        self.expected_dict["requestContext"].pop("time", None)
        self.expected_dict["requestContext"].pop("timeEpoch", None)

        self.assertEqual(actual_event, self.expected_dict)

    def test_v2_route_key(self):
        route_key = LocalApigwService._v2_route_key("GET", "/path", False)
        self.assertEqual(route_key, "GET /path")

    def test_v2_default_route_key(self):
        route_key = LocalApigwService._v2_route_key("GET", "/path", True)
        self.assertEqual(route_key, "$default")

    def test_event_headers_with_empty_list(self):
        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = []
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        actual_query_string = _event_http_headers(request_mock, "3000")
        self.assertEqual(actual_query_string, {"X-Forwarded-Proto": "http", "X-Forwarded-Port": "3000"})

    def test_event_headers_with_non_empty_list(self):
        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = ["Content-Type", "X-Test"]
        headers_mock.get.side_effect = ["application/json", "Value"]
        headers_mock.getlist.side_effect = [["application/json"], ["Value"]]
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        actual_query_string = _event_http_headers(request_mock, "3000")
        self.assertEqual(
            actual_query_string,
            {
                "Content-Type": "application/json",
                "X-Test": "Value",
                "X-Forwarded-Proto": "http",
                "X-Forwarded-Port": "3000",
            },
        )
