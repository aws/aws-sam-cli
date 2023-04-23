import base64
from datetime import datetime
import json
from time import time
from unittest import TestCase
from unittest.mock import Mock, patch
from parameterized import parameterized, param

from samcli.local.apigw.event_constructor import (
    _event_headers,
    _event_http_headers,
    _query_string_params,
    _query_string_params_v_2_0,
    _should_base64_encode,
    construct_v1_event,
    construct_v2_event_http,
)
from samcli.local.apigw.local_apigw_service import LocalApigwService


class TestService_construct_event(TestCase):
    def setUp(self):
        self.request_mock = Mock()
        self.request_mock.endpoint = "endpoint"
        self.request_mock.path = "path"
        self.request_mock.method = "GET"
        self.request_mock.remote_addr = "190.0.0.0"
        self.request_mock.host = "190.0.0.1"
        self.request_mock.get_data.return_value = b"DATA!!!!"
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

        expected = (
            '{"body": "DATA!!!!", "httpMethod": "GET", '
            '"multiValueQueryStringParameters": {"query": ["params"]}, '
            '"queryStringParameters": {"query": "params"}, "resource": '
            '"endpoint", "requestContext": {"httpMethod": "GET", "requestId": '
            '"c6af9ac6-7b61-11e6-9a41-93e8deadbeef", "path": "endpoint", "extendedRequestId": null, '
            '"resourceId": "123456", "apiId": "1234567890", "stage": null, "resourcePath": "endpoint", '
            '"identity": {"accountId": null, "apiKey": null, "userArn": null, '
            '"cognitoAuthenticationProvider": null, "cognitoIdentityPoolId": null, "userAgent": '
            '"Custom User Agent String", "caller": null, "cognitoAuthenticationType": null, "sourceIp": '
            '"190.0.0.0", "user": null}, "accountId": "123456789012", "domainName": "190.0.0.1", '
            '"protocol": "HTTP/1.1"}, "headers": {"Content-Type": '
            '"application/json", "X-Test": "Value", "X-Forwarded-Port": "3000", "X-Forwarded-Proto": "http"}, '
            '"multiValueHeaders": {"Content-Type": ["application/json"], "X-Test": ["Value"], '
            '"X-Forwarded-Port": ["3000"], "X-Forwarded-Proto": ["http"]}, '
            '"stageVariables": null, "path": "path", "pathParameters": {"path": "params"}, '
            '"isBase64Encoded": false}'
        )

        self.expected_dict = json.loads(expected)

    def validate_request_context_and_remove_request_time_data(self, event_json):
        request_time = event_json["requestContext"].pop("requestTime", None)
        request_time_epoch = event_json["requestContext"].pop("requestTimeEpoch", None)

        self.assertIsInstance(request_time, str)
        parsed_request_time = datetime.strptime(request_time, "%d/%b/%Y:%H:%M:%S +0000")
        self.assertIsInstance(parsed_request_time, datetime)

        self.assertIsInstance(request_time_epoch, int)

    def test_construct_event_with_data(self):
        actual_event_json = construct_v1_event(self.request_mock, 3000, binary_types=[])
        self.validate_request_context_and_remove_request_time_data(actual_event_json)

        self.assertEqual(actual_event_json["body"], self.expected_dict["body"])

    def test_construct_event_no_data(self):
        self.request_mock.get_data.return_value = None

        actual_event_json = construct_v1_event(self.request_mock, 3000, binary_types=[])
        self.validate_request_context_and_remove_request_time_data(actual_event_json)

        self.assertEqual(actual_event_json["body"], None)

    @patch("samcli.local.apigw.event_constructor._should_base64_encode")
    def test_construct_event_with_binary_data(self, should_base64_encode_patch):
        should_base64_encode_patch.return_value = True

        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")

        self.request_mock.get_data.return_value = binary_body

        actual_event_json = construct_v1_event(self.request_mock, 3000, binary_types=[])
        self.validate_request_context_and_remove_request_time_data(actual_event_json)

        self.assertEqual(actual_event_json["body"], base64_body)
        self.assertEqual(actual_event_json["isBase64Encoded"], True)

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


class TestService_construct_event_http(TestCase):
    def setUp(self):
        self.request_mock = Mock()
        self.request_mock.endpoint = "endpoint"
        self.request_mock.method = "GET"
        self.request_mock.path = "/endpoint"
        self.request_mock.get_data.return_value = b"DATA!!!!"
        self.request_mock.mimetype = "application/json"
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

        expected = f"""
        {{
            "version": "2.0",
            "routeKey": "GET /endpoint",
            "rawPath": "/endpoint",
            "rawQueryString": "query=params",
            "cookies": ["cookie1=test", "cookie2=test"],
            "headers": {{
                "Content-Type": "application/json",
                "X-Test": "Value",
                "X-Forwarded-Proto": "http",
                "X-Forwarded-Port": "3000"
            }},
            "queryStringParameters": {{"query": "param1,param2"}},
            "requestContext": {{
                "accountId": "123456789012",
                "apiId": "1234567890",
                "domainName": "localhost",
                "domainPrefix": "localhost",
                "http": {{
                    "method": "GET",
                    "path": "/endpoint",
                    "protocol": "HTTP/1.1",
                    "sourceIp": "190.0.0.0",
                    "userAgent": "Custom User Agent String"
                }},
                "requestId": "",
                "routeKey": "GET /endpoint",
                "stage": "$default",
                "time": \"{self.request_time}\",
                "timeEpoch": {self.request_time_epoch}
            }},
            "body": "DATA!!!!",
            "pathParameters": {{"path": "params"}},
            "stageVariables": null,
            "isBase64Encoded": false
        }}
        """

        self.expected_dict = json.loads(expected)

    def test_construct_event_with_data(self):
        actual_event_dict = construct_v2_event_http(
            self.request_mock,
            3000,
            binary_types=[],
            route_key="GET /endpoint",
            request_time_epoch=self.request_time_epoch,
            request_time=self.request_time,
        )
        self.assertEqual(len(actual_event_dict["requestContext"]["requestId"]), 36)
        actual_event_dict["requestContext"]["requestId"] = ""
        self.assertEqual(actual_event_dict, self.expected_dict)

    def test_construct_event_no_data(self):
        self.request_mock.get_data.return_value = None
        self.expected_dict["body"] = None

        actual_event_dict = construct_v2_event_http(
            self.request_mock,
            3000,
            binary_types=[],
            route_key="GET /endpoint",
            request_time_epoch=self.request_time_epoch,
            request_time=self.request_time,
        )
        self.assertEqual(len(actual_event_dict["requestContext"]["requestId"]), 36)
        actual_event_dict["requestContext"]["requestId"] = ""
        self.assertEqual(actual_event_dict, self.expected_dict)

    def test_v2_route_key(self):
        route_key = LocalApigwService._v2_route_key("GET", "/path", False)
        self.assertEqual(route_key, "GET /path")

    def test_v2_default_route_key(self):
        route_key = LocalApigwService._v2_route_key("GET", "/path", True)
        self.assertEqual(route_key, "$default")

    @patch("samcli.local.apigw.event_constructor._should_base64_encode")
    def test_construct_event_with_binary_data(self, should_base64_encode_patch):
        should_base64_encode_patch.return_value = True

        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")

        self.request_mock.get_data.return_value = binary_body
        self.expected_dict["body"] = base64_body
        self.expected_dict["isBase64Encoded"] = True
        self.maxDiff = None

        actual_event_dict = construct_v2_event_http(
            self.request_mock,
            3000,
            binary_types=[],
            route_key="GET /endpoint",
            request_time_epoch=self.request_time_epoch,
            request_time=self.request_time,
        )
        self.assertEqual(len(actual_event_dict["requestContext"]["requestId"]), 36)
        actual_event_dict["requestContext"]["requestId"] = ""
        self.assertEqual(actual_event_dict, self.expected_dict)

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


class TestService_should_base64_encode(TestCase):
    @parameterized.expand(
        [
            param("Mimeyype is in binary types", ["image/gif"], "image/gif"),
            param("Mimetype defined and binary types has */*", ["*/*"], "image/gif"),
            param("*/* is in binary types with no mimetype defined", ["*/*"], None),
        ]
    )
    def test_should_base64_encode_returns_true(self, test_case_name, binary_types, mimetype):
        self.assertTrue(_should_base64_encode(binary_types, mimetype))

    @parameterized.expand([param("Mimetype is not in binary types", ["image/gif"], "application/octet-stream")])
    def test_should_base64_encode_returns_false(self, test_case_name, binary_types, mimetype):
        self.assertFalse(_should_base64_encode(binary_types, mimetype))
