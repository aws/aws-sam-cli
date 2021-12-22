import base64
import copy
import json
from time import time
from datetime import datetime
from unittest import TestCase

from unittest.mock import Mock, patch, ANY, MagicMock
from parameterized import parameterized, param
from werkzeug.datastructures import Headers

from samcli.lib.providers.provider import Api
from samcli.lib.providers.provider import Cors
from samcli.local.apigw.local_apigw_service import (
    LocalApigwService,
    Route,
    LambdaResponseParseException,
    PayloadFormatVersionValidateException,
    CatchAllPathConverter,
)
from samcli.local.lambdafn.exceptions import FunctionNotFound


class TestApiGatewayService(TestCase):
    def setUp(self):
        self.function_name = Mock()
        self.api_gateway_route = Route(
            methods=["GET"],
            function_name=self.function_name,
            path="/",
            operation_name="getRestApi",
        )
        self.http_gateway_route = Route(
            methods=["GET"], function_name=self.function_name, path="/", event_type=Route.HTTP
        )
        self.http_v1_payload_route = Route(
            methods=["GET"],
            function_name=self.function_name,
            path="/v1",
            event_type=Route.HTTP,
            payload_format_version="1.0",
            operation_name="getV1",
        )
        self.http_v2_payload_route = Route(
            methods=["GET"],
            function_name=self.function_name,
            path="/v2",
            event_type=Route.HTTP,
            payload_format_version="2.0",
            operation_name="getV2",
        )
        self.http_v2_default_payload_route = Route(
            methods=["x-amazon-apigateway-any-method"],
            function_name=self.function_name,
            path="$default",
            event_type=Route.HTTP,
            payload_format_version="2.0",
            # no operation_name for default route
        )
        self.api_list_of_routes = [self.api_gateway_route]
        self.http_list_of_routes = [
            self.http_gateway_route,
            self.http_v1_payload_route,
            self.http_v2_payload_route,
            self.http_v2_default_payload_route,
        ]

        self.lambda_runner = Mock()
        self.lambda_runner.is_debugging.return_value = False

        self.stderr = Mock()
        self.api = Api(routes=self.api_list_of_routes)
        self.http = Api(routes=self.http_list_of_routes)
        self.api_service = LocalApigwService(
            self.api, self.lambda_runner, port=3000, host="127.0.0.1", stderr=self.stderr
        )
        self.http_service = LocalApigwService(
            self.http, self.lambda_runner, port=3000, host="127.0.0.1", stderr=self.stderr
        )

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    def test_api_request_must_invoke_lambda(self, request_mock):
        make_response_mock = Mock()

        self.api_service.service_response = make_response_mock
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value = self.api_gateway_route
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "2.0"
        self.api_service._construct_v_1_0_event = Mock()

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", Headers({"headers": "headers"}), "body")
        self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.api_service.service_response = service_response_mock

        request_mock.return_value = ("test", "test")

        result = self.api_service._request_handler()

        self.assertEqual(result, make_response_mock)
        self.lambda_runner.invoke.assert_called_with(ANY, ANY, stdout=ANY, stderr=self.stderr)
        self.api_service._construct_v_1_0_event.assert_called_with(ANY, ANY, ANY, ANY, ANY, "getRestApi")

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    def test_http_request_must_invoke_lambda(self, request_mock):
        make_response_mock = Mock()

        self.http_service.service_response = make_response_mock
        self.http_service._get_current_route = Mock()
        self.http_service._get_current_route.return_value = self.http_gateway_route
        self.http_service._get_current_route.methods = []
        self.http_service._construct_v_1_0_event = Mock()

        self.http_service._construct_v_2_0_event_http = MagicMock()

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", Headers({"headers": "headers"}), "body")
        self.http_service._parse_v2_payload_format_lambda_output = parse_output_mock

        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.http_service.service_response = service_response_mock

        request_mock.return_value = ("test", "test")

        result = self.http_service._request_handler()

        self.assertEqual(result, make_response_mock)
        self.lambda_runner.invoke.assert_called_with(ANY, ANY, stdout=ANY, stderr=self.stderr)
        self.http_service._construct_v_2_0_event_http.assert_called_with(ANY, ANY, ANY, ANY, ANY, ANY)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    def test_http_v1_payload_request_must_invoke_lambda(self, request_mock):
        make_response_mock = Mock()

        self.http_service.service_response = make_response_mock
        self.http_service._get_current_route = Mock()
        self.http_service._get_current_route.return_value = self.http_v1_payload_route
        self.http_service._get_current_route.methods = []
        self.http_service._construct_v_1_0_event = Mock()

        self.http_service._construct_v_2_0_event_http = MagicMock()

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", Headers({"headers": "headers"}), "body")
        self.http_service._parse_v1_payload_format_lambda_output = parse_output_mock

        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.http_service.service_response = service_response_mock

        request_mock.return_value = ("test", "test")

        result = self.http_service._request_handler()

        self.assertEqual(result, make_response_mock)
        self.lambda_runner.invoke.assert_called_with(ANY, ANY, stdout=ANY, stderr=self.stderr)
        self.http_service._construct_v_1_0_event.assert_called_with(ANY, ANY, ANY, ANY, ANY, None)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    def test_http_v2_payload_request_must_invoke_lambda(self, request_mock):
        make_response_mock = Mock()

        self.http_service.service_response = make_response_mock
        self.http_service._get_current_route = Mock()
        self.http_service._get_current_route.return_value = self.http_v2_payload_route
        self.http_service._get_current_route.methods = []
        self.http_service._construct_v_1_0_event = Mock()

        self.http_service._construct_v_2_0_event_http = MagicMock()

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", Headers({"headers": "headers"}), "body")
        self.http_service._parse_v2_payload_format_lambda_output = parse_output_mock

        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.http_service.service_response = service_response_mock

        request_mock.return_value = ("test", "test")

        result = self.http_service._request_handler()

        self.assertEqual(result, make_response_mock)
        self.lambda_runner.invoke.assert_called_with(ANY, ANY, stdout=ANY, stderr=self.stderr)
        self.http_service._construct_v_2_0_event_http.assert_called_with(ANY, ANY, ANY, ANY, ANY, ANY)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    def test_api_options_request_must_invoke_lambda(self, request_mock):
        make_response_mock = Mock()

        self.api_service.service_response = make_response_mock
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value.methods = ["OPTIONS"]
        self.api_service._get_current_route.return_value.payload_format_version = "1.0"
        self.api_service._construct_v_1_0_event = Mock()

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", Headers({"headers": "headers"}), "body")
        self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.api_service.service_response = service_response_mock

        request_mock.return_value = ("OPTIONS", "test")

        result = self.api_service._request_handler()

        self.assertEqual(result, make_response_mock)
        self.lambda_runner.invoke.assert_called_with(ANY, ANY, stdout=ANY, stderr=self.stderr)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    def test_http_options_request_must_invoke_lambda(self, request_mock):
        make_response_mock = Mock()

        self.http_service.service_response = make_response_mock
        self.http_service._get_current_route = MagicMock()
        self.http_service._get_current_route.return_value.methods = ["OPTIONS"]
        self.http_service._get_current_route.return_value.payload_format_version = "1.0"
        self.http_service._construct_v_1_0_event = Mock()

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", Headers({"headers": "headers"}), "body")
        self.http_service._parse_v1_payload_format_lambda_output = parse_output_mock

        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.http_service.service_response = service_response_mock

        request_mock.return_value = ("OPTIONS", "test")

        result = self.http_service._request_handler()

        self.assertEqual(result, make_response_mock)
        self.lambda_runner.invoke.assert_called_with(ANY, ANY, stdout=ANY, stderr=self.stderr)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.LambdaOutputParser")
    def test_request_handler_returns_process_stdout_when_making_response(self, lambda_output_parser_mock, request_mock):
        make_response_mock = Mock()
        request_mock.return_value = ("test", "test")
        self.api_service.service_response = make_response_mock
        current_route = Mock()
        current_route.payload_format_version = "2.0"
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value = current_route
        current_route.methods = []
        current_route.event_type = Route.API

        self.api_service._construct_v_1_0_event = Mock()

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", Headers({"headers": "headers"}), "body")
        self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

        lambda_logs = "logs"
        lambda_response = "response"
        is_customer_error = False
        lambda_output_parser_mock.get_lambda_output.return_value = lambda_response, lambda_logs, is_customer_error
        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.api_service.service_response = service_response_mock

        result = self.api_service._request_handler()

        self.assertEqual(result, make_response_mock)
        lambda_output_parser_mock.get_lambda_output.assert_called_with(ANY)

        # Make sure the parse method is called only on the returned response and not on the raw data from stdout
        parse_output_mock.assert_called_with(lambda_response, ANY, ANY, Route.API)
        # Make sure the logs are written to stderr
        self.stderr.write.assert_called_with(lambda_logs)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    def test_request_handler_returns_make_response(self, request_mock):
        make_response_mock = Mock()

        self.api_service.service_response = make_response_mock
        self.api_service._get_current_route = MagicMock()
        self.api_service._construct_v_1_0_event = Mock()
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "1.0"

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", Headers({"headers": "headers"}), "body")
        self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.api_service.service_response = service_response_mock

        request_mock.return_value = ("test", "test")
        result = self.api_service._request_handler()

        self.assertEqual(result, make_response_mock)

    def test_create_creates_dict_of_routes(self):
        function_name_1 = Mock()
        function_name_2 = Mock()
        function_name_3 = Mock()
        api_gateway_route_1 = Route(methods=["GET"], function_name=function_name_1, path="/")
        api_gateway_route_2 = Route(methods=["POST"], function_name=function_name_2, path="/")
        api_gateway_route_3 = Route(
            methods=["x-amazon-apigateway-any-method"], function_name=function_name_3, path="$default"
        )

        list_of_routes = [api_gateway_route_1, api_gateway_route_2, api_gateway_route_3]

        lambda_runner = Mock()

        api = Api(routes=list_of_routes)
        service = LocalApigwService(api, lambda_runner)

        service.create()

        self.assertEqual(service._dict_of_routes["/:GET"].function_name, function_name_1)
        self.assertEqual(service._dict_of_routes["/:POST"].function_name, function_name_2)
        self.assertEqual(service._dict_of_routes["/:OPTIONS"].function_name, function_name_3)
        self.assertEqual(service._dict_of_routes["/:PATCH"].function_name, function_name_3)
        self.assertEqual(service._dict_of_routes["/:DELETE"].function_name, function_name_3)
        self.assertEqual(service._dict_of_routes["/:PUT"].function_name, function_name_3)
        self.assertEqual(service._dict_of_routes["/<path:any_path>:GET"].function_name, function_name_3)
        self.assertEqual(service._dict_of_routes["/<path:any_path>:DELETE"].function_name, function_name_3)
        self.assertEqual(service._dict_of_routes["/<path:any_path>:PUT"].function_name, function_name_3)
        self.assertEqual(service._dict_of_routes["/<path:any_path>:POST"].function_name, function_name_3)
        self.assertEqual(service._dict_of_routes["/<path:any_path>:HEAD"].function_name, function_name_3)
        self.assertEqual(service._dict_of_routes["/<path:any_path>:OPTIONS"].function_name, function_name_3)
        self.assertEqual(service._dict_of_routes["/<path:any_path>:PATCH"].function_name, function_name_3)

    @patch("samcli.local.apigw.local_apigw_service.Flask")
    def test_create_creates_flask_app_with_url_rules(self, flask):
        app_mock = MagicMock()
        app_mock.config = {}
        flask.return_value = app_mock

        self.api_service._construct_error_handling = Mock()

        self.api_service.create()

        app_mock.add_url_rule.assert_called_once_with(
            "/",
            endpoint="/",
            view_func=self.api_service._request_handler,
            methods=["GET"],
            provide_automatic_options=False,
        )

    def test_api_initalize_creates_default_values(self):
        self.assertEqual(self.api_service.port, 3000)
        self.assertEqual(self.api_service.host, "127.0.0.1")
        self.assertEqual(self.api_service.api.routes, self.api_list_of_routes)
        self.assertIsNone(self.api_service.static_dir)
        self.assertEqual(self.api_service.lambda_runner, self.lambda_runner)

    def test_http_initalize_creates_default_values(self):
        self.assertEqual(self.http_service.port, 3000)
        self.assertEqual(self.http_service.host, "127.0.0.1")
        self.assertEqual(self.http_service.api.routes, self.http_list_of_routes)
        self.assertIsNone(self.http_service.static_dir)
        self.assertEqual(self.http_service.lambda_runner, self.lambda_runner)

    def test_initalize_with_values(self):
        lambda_runner = Mock()
        local_service = LocalApigwService(Api(), lambda_runner, static_dir="dir/static", port=5000, host="129.0.0.0")
        self.assertEqual(local_service.port, 5000)
        self.assertEqual(local_service.host, "129.0.0.0")
        self.assertEqual(local_service.api.routes, [])
        self.assertEqual(local_service.static_dir, "dir/static")
        self.assertEqual(local_service.lambda_runner, lambda_runner)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    def test_request_handles_error_when_invoke_cant_find_function(self, service_error_responses_patch, request_mock):
        not_found_response_mock = Mock()
        self.api_service._construct_v_1_0_event = Mock()
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value.payload_format_version = "2.0"
        self.api_service._get_current_route.methods = []

        service_error_responses_patch.lambda_not_found_response.return_value = not_found_response_mock

        self.lambda_runner.invoke.side_effect = FunctionNotFound()
        request_mock.return_value = ("test", "test")
        response = self.api_service._request_handler()

        self.assertEqual(response, not_found_response_mock)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    def test_request_throws_when_invoke_fails(self, request_mock):
        self.lambda_runner.invoke.side_effect = Exception()

        self.api_service._construct_v_1_0_event = Mock()
        self.api_service._get_current_route = Mock()
        request_mock.return_value = ("test", "test")

        with self.assertRaises(Exception):
            self.api_service._request_handler()

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    def test_request_handler_errors_when_parse_lambda_output_raises_keyerror(
        self, service_error_responses_patch, request_mock
    ):
        parse_output_mock = Mock()
        parse_output_mock.side_effect = LambdaResponseParseException()
        self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

        failure_response_mock = Mock()

        service_error_responses_patch.lambda_failure_response.return_value = failure_response_mock

        self.api_service._construct_v_1_0_event = Mock()
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "1.0"

        request_mock.return_value = ("test", "test")
        result = self.api_service._request_handler()

        self.assertEqual(result, failure_response_mock)

    @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    def test_request_handler_errors_when_get_current_route_fails(self, service_error_responses_patch):
        get_current_route = Mock()
        get_current_route.side_effect = KeyError()
        self.api_service._get_current_route = get_current_route

        with self.assertRaises(KeyError):
            self.api_service._request_handler()

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    def test_request_handler_errors_when_unable_to_read_binary_data(self, service_error_responses_patch, request_mock):
        _construct_event = Mock()
        _construct_event.side_effect = UnicodeDecodeError("utf8", b"obj", 1, 2, "reason")
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "1.0"

        self.api_service._construct_v_1_0_event = _construct_event

        failure_mock = Mock()
        service_error_responses_patch.lambda_failure_response.return_value = failure_mock

        request_mock.return_value = ("test", "test")
        result = self.api_service._request_handler()
        self.assertEqual(result, failure_mock)

    @parameterized.expand([param("1.5"), param(2.0)])
    def test_request_handler_errors_when_payload_format_version_wrong(self, payload_format_version):
        get_current_route = Mock()
        get_current_route.return_value.payload_format_version = payload_format_version
        self.api_service._get_current_route = get_current_route

        with self.assertRaises(PayloadFormatVersionValidateException):
            self.api_service._request_handler()

    def test_get_current_route(self):
        request_mock = Mock()
        request_mock.return_value.endpoint = "path"
        request_mock.return_value.method = "method"

        route_key_method_mock = Mock()
        route_key_method_mock.return_value = "method:path"
        self.api_service._route_key = route_key_method_mock
        self.api_service._dict_of_routes = {"method:path": "function"}

        self.assertEqual(self.api_service._get_current_route(request_mock), "function")

    def test_get_current_route_keyerror(self):
        """
        When the a HTTP request for given method+path combination is allowed by Flask but not in the list of routes,
        something is messed up. Flask should be configured only from the list of routes.
        """

        request_mock = Mock()
        request_mock.endpoint = "path"
        request_mock.method = "method"

        route_key_method_mock = Mock()
        route_key_method_mock.return_value = "method:path"
        self.api_service._route_key = route_key_method_mock
        self.api_service._dict_of_routes = {"a": "b"}

        with self.assertRaises(KeyError):
            self.api_service._get_current_route(request_mock)


class TestApiGatewayModel(TestCase):
    def setUp(self):
        self.function_name = "name"
        self.api_gateway = Route(function_name=self.function_name, methods=["Post"], path="/")
        self.http_gateway = Route(function_name=self.function_name, methods=["Post"], path="/", event_type=Route.HTTP)

    def test_class_initialization(self):
        self.assertEqual(self.api_gateway.methods, ["POST"])
        self.assertEqual(self.api_gateway.function_name, self.function_name)
        self.assertEqual(self.api_gateway.path, "/")
        self.assertEqual(self.api_gateway.event_type, Route.API)

    def test_class_initialization_http(self):
        self.assertEqual(self.http_gateway.methods, ["POST"])
        self.assertEqual(self.http_gateway.function_name, self.function_name)
        self.assertEqual(self.http_gateway.path, "/")
        self.assertEqual(self.http_gateway.event_type, Route.HTTP)


class TestLambdaHeaderDictionaryMerge(TestCase):
    def test_empty_dictionaries_produce_empty_result(self):
        headers = {}
        multi_value_headers = {}

        result = LocalApigwService._merge_response_headers(headers, multi_value_headers)

        self.assertEqual(result, Headers({}))

    def test_headers_are_merged(self):
        headers = {"h1": "value1", "h2": "value2", "h3": "value3"}
        multi_value_headers = {"h3": ["value4"]}

        result = LocalApigwService._merge_response_headers(headers, multi_value_headers)

        self.assertIn("h1", result)
        self.assertIn("h2", result)
        self.assertIn("h3", result)
        self.assertEqual(result["h1"], "value1")
        self.assertEqual(result["h2"], "value2")
        self.assertEqual(result.get_all("h3"), ["value4", "value3"])

    def test_merge_does_not_duplicate_values(self):
        headers = {"h1": "ValueB"}
        multi_value_headers = {"h1": ["ValueA", "ValueB", "ValueC"]}

        result = LocalApigwService._merge_response_headers(headers, multi_value_headers)

        self.assertIn("h1", result)
        self.assertEqual(result.get_all("h1"), ["ValueA", "ValueB", "ValueC"])


class TestServiceParsingV1PayloadFormatLambdaOutput(TestCase):
    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_default_content_type_header_added_with_no_headers(self, event_type):
        lambda_output = (
            '{"statusCode": 200, "body": "{\\"message\\":\\"Hello from Lambda\\"}", ' '"isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
        )

        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["Content-Type"], "application/json")

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_default_content_type_header_added_with_empty_headers(self, event_type):
        lambda_output = (
            '{"statusCode": 200, "headers":{}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
        )

        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["Content-Type"], "application/json")

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_custom_content_type_header_is_not_modified(self, event_type):
        lambda_output = (
            '{"statusCode": 200, "headers":{"Content-Type": "text/xml"}, "body": "{}", ' '"isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
        )

        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["Content-Type"], "text/xml")

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_custom_content_type_multivalue_header_is_not_modified(self, event_type):
        lambda_output = (
            '{"statusCode": 200, "multiValueHeaders":{"Content-Type": ["text/xml"]}, "body": "{}", '
            '"isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
        )

        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["Content-Type"], "text/xml")

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_multivalue_headers(self, event_type):
        lambda_output = (
            '{"statusCode": 200, "multiValueHeaders":{"X-Foo": ["bar", "42"]}, '
            '"body": "{\\"message\\":\\"Hello from Lambda\\"}", "isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
        )

        self.assertEqual(headers, Headers({"Content-Type": "application/json", "X-Foo": ["bar", "42"]}))

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_single_and_multivalue_headers(self, event_type):
        lambda_output = (
            '{"statusCode": 200, "headers":{"X-Foo": "foo", "X-Bar": "bar"}, '
            '"multiValueHeaders":{"X-Foo": ["bar", "42"]}, '
            '"body": "{\\"message\\":\\"Hello from Lambda\\"}", "isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
        )

        self.assertEqual(
            headers, Headers({"Content-Type": "application/json", "X-Bar": "bar", "X-Foo": ["bar", "42", "foo"]})
        )

    def test_extra_values_raise(self):
        lambda_output = (
            '{"statusCode": 200, "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false, "base64Encoded": false, "another_key": "some value"}'
        )

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v1_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock(), event_type=Route.API
            )

    def test_extra_values_skipped_http_api(self):
        lambda_output = (
            '{"statusCode": 200, "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false, "another_key": "some value"}'
        )

        (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=Route.HTTP
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/json"}))
        self.assertEqual(body, '{"message":"Hello from Lambda"}')

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_parse_returns_correct_tuple(self, event_type):
        lambda_output = (
            '{"statusCode": 200, "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/json"}))
        self.assertEqual(body, '{"message":"Hello from Lambda"}')

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_parse_raises_when_invalid_mimetype(self, event_type):
        lambda_output = (
            '{"statusCode": 200, "headers": {\\"Content-Type\\": \\"text\\"}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v1_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
            )

    @parameterized.expand(
        [
            param("isBase64Encoded", True, True),
            param("base64Encoded", True, True),
            param("isBase64Encoded", False, False),
            param("base64Encoded", False, False),
            param("isBase64Encoded", "True", True),
            param("base64Encoded", "True", True),
            param("isBase64Encoded", "true", True),
            param("base64Encoded", "true", True),
            param("isBase64Encoded", "False", False),
            param("base64Encoded", "False", False),
            param("isBase64Encoded", "false", False),
            param("base64Encoded", "false", False),
        ]
    )
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._should_base64_decode_body")
    def test_parse_returns_decodes_base64_to_binary_for_rest_api(
        self, encoded_field_name, encoded_response_value, encoded_parsed_value, should_decode_body_patch
    ):
        should_decode_body_patch.return_value = True

        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")
        lambda_output = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/octet-stream"},
            "body": base64_body,
            encoded_field_name: encoded_response_value,
        }

        flask_request_mock = Mock()
        (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
            json.dumps(lambda_output), binary_types=["*/*"], flask_request=flask_request_mock, event_type=Route.API
        )

        should_decode_body_patch.assert_called_with(
            ["*/*"], flask_request_mock, Headers({"Content-Type": "application/octet-stream"}), encoded_parsed_value
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/octet-stream"}))
        self.assertEqual(body, binary_body)

    @parameterized.expand(
        [
            param("isBase64Encoded", 0),
            param("base64Encoded", 0),
            param("isBase64Encoded", 1),
            param("base64Encoded", 1),
            param("isBase64Encoded", -1),
            param("base64Encoded", -1),
            param("isBase64Encoded", 10),
            param("base64Encoded", 10),
            param("isBase64Encoded", "TRue"),
            param("base64Encoded", "TRue"),
            param("isBase64Encoded", "Any Value"),
            param("base64Encoded", "Any Value"),
        ]
    )
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._should_base64_decode_body")
    def test_parse_raise_exception_invalide_base64_encoded(
        self, encoded_field_name, encoded_response_value, should_decode_body_patch
    ):
        should_decode_body_patch.return_value = True

        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")
        lambda_output = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/octet-stream"},
            "body": base64_body,
            encoded_field_name: encoded_response_value,
        }

        flask_request_mock = Mock()
        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v1_payload_format_lambda_output(
                json.dumps(lambda_output), binary_types=["*/*"], flask_request=flask_request_mock, event_type=Route.API
            )

    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._should_base64_decode_body")
    def test_parse_base64Encoded_field_is_priority(self, should_decode_body_patch):
        should_decode_body_patch.return_value = True

        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")
        lambda_output = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/octet-stream"},
            "body": base64_body,
            "isBase64Encoded": False,
            "base64Encoded": True,
        }

        flask_request_mock = Mock()
        (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
            json.dumps(lambda_output), binary_types=["*/*"], flask_request=flask_request_mock, event_type=Route.API
        )

        should_decode_body_patch.assert_called_with(
            ["*/*"], flask_request_mock, Headers({"Content-Type": "application/octet-stream"}), True
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/octet-stream"}))
        self.assertEqual(body, binary_body)

    @parameterized.expand(
        [
            param(True, True),
            param(False, False),
            param("True", True),
            param("true", True),
            param("False", False),
            param("false", False),
        ]
    )
    def test_parse_returns_decodes_base64_to_binary_for_http_api(self, encoded_response_value, encoded_parsed_value):
        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")
        lambda_output = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/octet-stream"},
            "body": base64_body,
            "isBase64Encoded": encoded_response_value,
        }

        (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
            json.dumps(lambda_output), binary_types=["*/*"], flask_request=Mock(), event_type=Route.HTTP
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/octet-stream"}))
        self.assertEqual(body, binary_body if encoded_parsed_value else base64_body)

    @parameterized.expand(
        [
            param(0),
            param(1),
            param(-1),
            param(10),
            param("TRue"),
            param("Any Value"),
        ]
    )
    def test_parse_raise_exception_invalide_base64_encoded_for_http_api(self, encoded_response_value):

        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")
        lambda_output = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/octet-stream"},
            "body": base64_body,
            "isBase64Encoded": encoded_response_value,
        }

        flask_request_mock = Mock()
        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v1_payload_format_lambda_output(
                json.dumps(lambda_output), binary_types=["*/*"], flask_request=flask_request_mock, event_type=Route.API
            )

    @parameterized.expand(
        [
            param(True),
            param(False),
            param("True"),
            param("true"),
            param("False"),
            param("false"),
            param(0),
            param(1),
            param(-1),
            param(10),
            param("TRue"),
            param("Any Value"),
        ]
    )
    def test_parse_skip_base_64_encoded_field_http_api(self, encoded_response_value):
        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")
        lambda_output = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/octet-stream"},
            "body": base64_body,
            "base64Encoded": encoded_response_value,
        }

        (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
            json.dumps(lambda_output), binary_types=["*/*"], flask_request=Mock(), event_type=Route.HTTP
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/octet-stream"}))
        self.assertEqual(body, base64_body)

    def test_parse_returns_does_not_decodes_base64_to_binary_for_http_api(self):
        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")
        lambda_output = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/octet-stream"},
            "body": base64_body,
            "isBase64Encoded": False,
        }

        (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
            json.dumps(lambda_output), binary_types=["*/*"], flask_request=Mock(), event_type=Route.HTTP
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/octet-stream"}))
        self.assertEqual(body, base64_body)

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_status_code_not_int(self, event_type):
        lambda_output = (
            '{"statusCode": "str", "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v1_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
            )

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_status_code_int_str(self, event_type):
        lambda_output = (
            '{"statusCode": "200", "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        (status_code, _, _) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
        )
        self.assertEqual(status_code, 200)

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_status_code_negative_int(self, event_type):
        lambda_output = (
            '{"statusCode": -1, "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v1_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
            )

    def test_status_code_is_none_http_api(self):
        lambda_output = (
            '{"headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", ' '"isBase64Encoded": false}'
        )

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v1_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock(), event_type=Route.HTTP
            )

    def test_status_code_is_none_rest_api(self):
        lambda_output = (
            '{"headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", ' '"isBase64Encoded": false}'
        )

        (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=Route.API
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/json"}))
        self.assertEqual(body, '{"message":"Hello from Lambda"}')

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_status_code_negative_int_str(self, event_type):
        lambda_output = (
            '{"statusCode": "-1", "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v1_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
            )

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_lambda_output_list_not_dict(self, event_type):
        lambda_output = "[]"

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v1_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
            )

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_lambda_output_not_json_serializable(self, event_type):
        lambda_output = "some str"

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v1_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
            )

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_properties_are_null(self, event_type):
        lambda_output = '{"statusCode": 0, "headers": null, "body": null, ' '"isBase64Encoded": null}'

        (status_code, headers, body) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/json"}))
        self.assertEqual(body, None)

    @parameterized.expand(
        [
            param(Route.API),
            param(Route.HTTP),
        ]
    )
    def test_cookies_is_not_raise(self, event_type):
        lambda_output = (
            '{"statusCode": 200, "headers":{}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false, "cookies":{}}'
        )

        (_, headers, _) = LocalApigwService._parse_v1_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock(), event_type=event_type
        )


class TestServiceParsingV2PayloadFormatLambdaOutput(TestCase):
    def test_default_content_type_header_added_with_no_headers(self):
        lambda_output = (
            '{"statusCode": 200, "body": "{\\"message\\":\\"Hello from Lambda\\"}", ' '"isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )

        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_default_content_type_header_added_with_empty_headers(self):
        lambda_output = (
            '{"statusCode": 200, "headers":{}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )

        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_custom_content_type_header_is_not_modified(self):
        lambda_output = (
            '{"statusCode": 200, "headers":{"Content-Type": "text/xml"}, "body": "{}", ' '"isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )

        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["Content-Type"], "text/xml")

    def test_custom_cookies_in_payload_format_version_2(self):
        lambda_output = (
            '{"statusCode": 200, "cookies": ["cookie1=test1", "cookie2=test2"], "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )

        self.assertEqual(headers.getlist("Set-Cookie"), ["cookie1=test1", "cookie2=test2"])

    def test_invalid_cookies_in_payload_format_version_2(self):
        lambda_output = (
            '{"statusCode": 200, "cookies": "cookies1=test1", "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )

        self.assertNotIn("Set-Cookie", headers)

    def test_existed_cookies_in_payload_format_version_2(self):
        lambda_output = (
            '{"statusCode": 200, "headers":{"Set-Cookie": "cookie1=test1"}, "cookies": ["cookie2=test2", "cookie3=test3"], "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        (_, headers, _) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )

        self.assertEqual(headers.getlist("Set-Cookie"), ["cookie1=test1", "cookie2=test2", "cookie3=test3"])

    def test_extra_values_skipped(self):
        lambda_output = (
            '{"statusCode": 200, "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false, "another_key": "some value"}'
        )

        (status_code, headers, body) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/json"}))
        self.assertEqual(body, '{"message":"Hello from Lambda"}')

    def test_parse_returns_correct_tuple(self):
        lambda_output = (
            '{"statusCode": 200, "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        (status_code, headers, body) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/json"}))
        self.assertEqual(body, '{"message":"Hello from Lambda"}')

    def test_parse_raises_when_invalid_mimetype(self):
        lambda_output = (
            '{"statusCode": 200, "headers": {\\"Content-Type\\": \\"text\\"}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v2_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock()
            )

    def test_parse_returns_does_not_decodes_base64_to_binary(self):
        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")
        lambda_output = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/octet-stream"},
            "body": base64_body,
            "isBase64Encoded": False,
        }

        (status_code, headers, body) = LocalApigwService._parse_v2_payload_format_lambda_output(
            json.dumps(lambda_output), binary_types=["*/*"], flask_request=Mock()
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/octet-stream"}))
        self.assertEqual(body, base64_body)

    def test_parse_returns_decodes_base64_to_binary(self):
        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")
        lambda_output = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/octet-stream"},
            "body": base64_body,
            "isBase64Encoded": True,
        }

        (status_code, headers, body) = LocalApigwService._parse_v2_payload_format_lambda_output(
            json.dumps(lambda_output), binary_types=["*/*"], flask_request=Mock()
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/octet-stream"}))
        self.assertEqual(body, binary_body)

    def test_status_code_int_str(self):
        lambda_output = (
            '{"statusCode": "200", "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        (status_code, _, _) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )
        self.assertEqual(status_code, 200)

    def test_status_code_negative_int(self):
        lambda_output = (
            '{"statusCode": -1, "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v2_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock()
            )

    def test_status_code_negative_int_str(self):
        lambda_output = (
            '{"statusCode": "-1", "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", '
            '"isBase64Encoded": false}'
        )

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v2_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock()
            )

    def test_lambda_output_invalid_json(self):
        lambda_output = "{{}"

        with self.assertRaises(LambdaResponseParseException):
            LocalApigwService._parse_v2_payload_format_lambda_output(
                lambda_output, binary_types=[], flask_request=Mock()
            )

    def test_lambda_output_string(self):
        lambda_output = '"some str"'
        (status_code, headers, body) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/json"}))
        self.assertEqual(body, "some str")

    def test_lambda_output_integer(self):
        lambda_output = "2"
        (status_code, headers, body) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/json"}))
        self.assertEqual(body, lambda_output)

    def test_properties_are_null(self):
        lambda_output = '{"statusCode": 0, "headers": null, "body": null, ' '"isBase64Encoded": null}'

        (status_code, headers, body) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/json"}))
        self.assertEqual(body, None)

    def test_lambda_output_json_object_no_status_code(self):
        lambda_output = '{"message": "Hello from Lambda!"}'

        (status_code, headers, body) = LocalApigwService._parse_v2_payload_format_lambda_output(
            lambda_output, binary_types=[], flask_request=Mock()
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers, Headers({"Content-Type": "application/json"}))
        self.assertEqual(body, lambda_output)


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
        actual_event_str = LocalApigwService._construct_v_1_0_event(self.request_mock, 3000, binary_types=[])

        actual_event_json = json.loads(actual_event_str)
        self.validate_request_context_and_remove_request_time_data(actual_event_json)

        self.assertEqual(actual_event_json["body"], self.expected_dict["body"])

    def test_construct_event_no_data(self):
        self.request_mock.get_data.return_value = None

        actual_event_str = LocalApigwService._construct_v_1_0_event(self.request_mock, 3000, binary_types=[])
        actual_event_json = json.loads(actual_event_str)
        self.validate_request_context_and_remove_request_time_data(actual_event_json)

        self.assertEqual(actual_event_json["body"], None)

    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._should_base64_encode")
    def test_construct_event_with_binary_data(self, should_base64_encode_patch):
        should_base64_encode_patch.return_value = True

        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")

        self.request_mock.get_data.return_value = binary_body

        actual_event_str = LocalApigwService._construct_v_1_0_event(self.request_mock, 3000, binary_types=[])
        actual_event_json = json.loads(actual_event_str)
        self.validate_request_context_and_remove_request_time_data(actual_event_json)

        self.assertEqual(actual_event_json["body"], base64_body)
        self.assertEqual(actual_event_json["isBase64Encoded"], True)

    def test_event_headers_with_empty_list(self):
        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = []
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        actual_query_string = LocalApigwService._event_headers(request_mock, "3000")
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

        actual_query_string = LocalApigwService._event_headers(request_mock, "3000")
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

        actual_query_string = LocalApigwService._query_string_params(request_mock)
        self.assertEqual(actual_query_string, ({}, {}))

    def test_query_string_params_with_param_value_being_empty_list(self):
        request_mock = Mock()
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"param": []}.items()
        request_mock.args = query_param_args_mock

        actual_query_string = LocalApigwService._query_string_params(request_mock)
        self.assertEqual(actual_query_string, ({"param": ""}, {"param": [""]}))

    def test_query_string_params_with_param_value_being_non_empty_list(self):
        request_mock = Mock()
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"param": ["a", "b"]}.items()
        request_mock.args = query_param_args_mock

        actual_query_string = LocalApigwService._query_string_params(request_mock)
        self.assertEqual(actual_query_string, ({"param": "b"}, {"param": ["a", "b"]}))


class TestService_construct_event_http(TestCase):
    def setUp(self):
        self.request_mock = Mock()
        self.request_mock.endpoint = "endpoint"
        self.request_mock.method = "GET"
        self.request_mock.path = "/endpoint"
        self.request_mock.get_data.return_value = b"DATA!!!!"
        self.request_mock.mimetype = "application/json"
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"query": ["params"]}.items()
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
            "queryStringParameters": {{"query": "params"}},
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
        actual_event_str = LocalApigwService._construct_v_2_0_event_http(
            self.request_mock,
            3000,
            binary_types=[],
            route_key="GET /endpoint",
            request_time_epoch=self.request_time_epoch,
            request_time=self.request_time,
        )
        print("DEBUG: json.loads(actual_event_str)", json.loads(actual_event_str))
        print("DEBUG: self.expected_dict", self.expected_dict)
        actual_event_dict = json.loads(actual_event_str)
        self.assertEqual(len(actual_event_dict["requestContext"]["requestId"]), 36)
        actual_event_dict["requestContext"]["requestId"] = ""
        self.assertEqual(actual_event_dict, self.expected_dict)

    def test_construct_event_no_data(self):
        self.request_mock.get_data.return_value = None
        self.expected_dict["body"] = None

        actual_event_str = LocalApigwService._construct_v_2_0_event_http(
            self.request_mock,
            3000,
            binary_types=[],
            route_key="GET /endpoint",
            request_time_epoch=self.request_time_epoch,
            request_time=self.request_time,
        )
        actual_event_dict = json.loads(actual_event_str)
        self.assertEqual(len(actual_event_dict["requestContext"]["requestId"]), 36)
        actual_event_dict["requestContext"]["requestId"] = ""
        self.assertEqual(actual_event_dict, self.expected_dict)

    def test_v2_route_key(self):
        route_key = LocalApigwService._v2_route_key("GET", "/path", False)
        self.assertEqual(route_key, "GET /path")

    def test_v2_default_route_key(self):
        route_key = LocalApigwService._v2_route_key("GET", "/path", True)
        self.assertEqual(route_key, "$default")

    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._should_base64_encode")
    def test_construct_event_with_binary_data(self, should_base64_encode_patch):
        should_base64_encode_patch.return_value = True

        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode("utf-8")

        self.request_mock.get_data.return_value = binary_body
        self.expected_dict["body"] = base64_body
        self.expected_dict["isBase64Encoded"] = True
        self.maxDiff = None

        actual_event_str = LocalApigwService._construct_v_2_0_event_http(
            self.request_mock,
            3000,
            binary_types=[],
            route_key="GET /endpoint",
            request_time_epoch=self.request_time_epoch,
            request_time=self.request_time,
        )
        actual_event_dict = json.loads(actual_event_str)
        self.assertEqual(len(actual_event_dict["requestContext"]["requestId"]), 36)
        actual_event_dict["requestContext"]["requestId"] = ""
        self.assertEqual(actual_event_dict, self.expected_dict)

    def test_event_headers_with_empty_list(self):
        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = []
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        actual_query_string = LocalApigwService._event_http_headers(request_mock, "3000")
        self.assertEqual(actual_query_string, {"X-Forwarded-Proto": "http", "X-Forwarded-Port": "3000"})

    def test_event_headers_with_non_empty_list(self):
        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = ["Content-Type", "X-Test"]
        headers_mock.get.side_effect = ["application/json", "Value"]
        headers_mock.getlist.side_effect = [["application/json"], ["Value"]]
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        actual_query_string = LocalApigwService._event_http_headers(request_mock, "3000")
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
        self.assertTrue(LocalApigwService._should_base64_encode(binary_types, mimetype))

    @parameterized.expand([param("Mimetype is not in binary types", ["image/gif"], "application/octet-stream")])
    def test_should_base64_encode_returns_false(self, test_case_name, binary_types, mimetype):
        self.assertFalse(LocalApigwService._should_base64_encode(binary_types, mimetype))


class TestServiceCorsToHeaders(TestCase):
    def test_basic_conversion(self):
        cors = Cors(
            allow_origin="*", allow_methods=",".join(["POST", "OPTIONS"]), allow_headers="UPGRADE-HEADER", max_age=6
        )
        headers = Cors.cors_to_headers(cors)

        self.assertEqual(
            headers,
            {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
                "Access-Control-Allow-Headers": "UPGRADE-HEADER",
                "Access-Control-Max-Age": 6,
            },
        )

    def test_empty_elements(self):
        cors = Cors(allow_origin="www.domain.com", allow_methods=",".join(["GET", "POST", "OPTIONS"]))
        headers = Cors.cors_to_headers(cors)

        self.assertEqual(
            headers,
            {"Access-Control-Allow-Origin": "www.domain.com", "Access-Control-Allow-Methods": "GET,POST,OPTIONS"},
        )


class TestRouteEqualsHash(TestCase):
    def test_route_in_list(self):
        route = Route(function_name="test", path="/test", methods=["POST"])
        routes = [route]
        self.assertIn(route, routes)

    def test_route_method_order_equals(self):
        route1 = Route(function_name="test", path="/test", methods=["POST", "GET"])
        route2 = Route(function_name="test", path="/test", methods=["GET", "POST"])
        self.assertEqual(route1, route2)

    def test_route_hash(self):
        route1 = Route(function_name="test", path="/test", methods=["POST", "GET"])
        dic = {route1: "test"}
        self.assertEqual(dic[route1], "test")

    def test_route_object_equals(self):
        route1 = Route(function_name="test", path="/test", methods=["POST", "GET"])
        route2 = type("obj", (object,), {"function_name": "test", "path": "/test", "methods": ["GET", "POST"]})

        self.assertNotEqual(route1, route2)

    def test_route_function_name_equals(self):
        route1 = Route(function_name="test1", path="/test", methods=["GET", "POST"])
        route2 = Route(function_name="test2", path="/test", methods=["GET", "POST"])
        self.assertNotEqual(route1, route2)

    def test_route_different_path_equals(self):
        route1 = Route(function_name="test", path="/test1", methods=["GET", "POST"])
        route2 = Route(function_name="test", path="/test2", methods=["GET", "POST"])
        self.assertNotEqual(route1, route2)

    def test_same_object_equals(self):
        route1 = Route(function_name="test", path="/test", methods=["POST", "GET"])
        self.assertEqual(route1, copy.deepcopy(route1))

    def test_route_function_name_hash(self):
        route1 = Route(function_name="test1", path="/test", methods=["GET", "POST"])
        route2 = Route(function_name="test2", path="/test", methods=["GET", "POST"])
        self.assertNotEqual(route1.__hash__(), route2.__hash__())

    def test_route_different_path_hash(self):
        route1 = Route(function_name="test", path="/test1", methods=["GET", "POST"])
        route2 = Route(function_name="test", path="/test2", methods=["GET", "POST"])
        self.assertNotEqual(route1.__hash__(), route2.__hash__())

    def test_same_object_hash(self):
        route1 = Route(function_name="test", path="/test", methods=["POST", "GET"])
        self.assertEqual(route1.__hash__(), copy.deepcopy(route1).__hash__())

    def test_route_method_order_hash(self):
        route1 = Route(function_name="test", path="/test", methods=["POST", "GET"])
        route2 = Route(function_name="test", path="/test", methods=["GET", "POST"])
        self.assertEqual(route1.__hash__(), route2.__hash__())

    def test_route_different_stack_path_hash(self):
        route1 = Route(function_name="test", path="/test1", methods=["GET", "POST"], stack_path="2")
        route2 = Route(function_name="test", path="/test1", methods=["GET", "POST"], stack_path="1")
        self.assertNotEqual(route1.__hash__(), route2.__hash__())


class TestPathConverter(TestCase):
    def test_path_converter_to_url_accepts_any_path(self):
        map = Mock()
        map.charset = "utf-8"
        path_converter = CatchAllPathConverter(map)
        path = "/path/test/sub_path"
        output = path_converter.to_url(path)
        self.assertEquals(path, output)

    def test_path_converter_to_python_accepts_any_path(self):
        map = Mock()
        map.charset = "utf-8"
        path_converter = CatchAllPathConverter(map)
        path = "/path/test/sub_path"
        output = path_converter.to_python(path)
        self.assertEquals(path, output)

    def test_path_converter_matches_any_path(self):
        map = Mock()
        map.charset = "utf-8"
        path_converter = CatchAllPathConverter(map)
        path = "/path/test/sub_path"
        self.assertRegexpMatches(path, path_converter.regex)
