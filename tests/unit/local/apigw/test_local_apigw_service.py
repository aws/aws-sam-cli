import base64
import copy
import json
import flask
from unittest import TestCase

from unittest.mock import Mock, patch, ANY, MagicMock
from parameterized import parameterized, param
from werkzeug.datastructures import Headers

from samcli.lib.providers.provider import Api
from samcli.lib.providers.provider import Cors
from samcli.lib.telemetry.event import EventName, EventTracker, UsedFeature
from samcli.local.apigw.event_constructor import construct_v1_event, construct_v2_event_http
from samcli.local.apigw.authorizers.lambda_authorizer import LambdaAuthorizer
from samcli.local.apigw.route import Route
from samcli.local.apigw.local_apigw_service import (
    LocalApigwService,
    CatchAllPathConverter,
)
from samcli.local.apigw.exceptions import (
    AuthorizerUnauthorizedRequest,
    InvalidSecurityDefinition,
    LambdaResponseParseException,
    PayloadFormatVersionValidateException,
)
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.commands.local.lib.exceptions import UnsupportedInlineCodeError


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
    @patch("samcli.local.apigw.local_apigw_service.construct_v1_event")
    @patch("samcli.local.apigw.local_apigw_service.construct_v2_event_http")
    def test_api_request_must_invoke_lambda(self, v2_event_mock, v1_event_mock, request_mock):
        make_response_mock = Mock()

        self.api_service.service_response = make_response_mock
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value = self.api_gateway_route
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "2.0"
        v1_event_mock.return_value = {}

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
        v1_event_mock.assert_called_with(
            flask_request=ANY,
            port=ANY,
            binary_types=ANY,
            stage_name=ANY,
            stage_variables=ANY,
            operation_name="getRestApi",
        )

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.construct_v1_event")
    @patch("samcli.local.apigw.local_apigw_service.construct_v2_event_http")
    def test_http_request_must_invoke_lambda(self, v2_event_mock, v1_event_mock, request_mock):
        make_response_mock = Mock()

        self.http_service.service_response = make_response_mock
        self.http_service._get_current_route = Mock()
        self.http_service._get_current_route.return_value = self.http_gateway_route
        self.http_service._get_current_route.methods = []

        v2_event_mock.return_value = {}

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
        v2_event_mock.assert_called_with(
            flask_request=ANY, port=ANY, binary_types=ANY, stage_name=ANY, stage_variables=ANY, route_key="test test"
        )

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.construct_v1_event")
    @patch("samcli.local.apigw.local_apigw_service.construct_v2_event_http")
    def test_http_v1_payload_request_must_invoke_lambda(self, v2_event_mock, v1_event_mock, request_mock):
        make_response_mock = Mock()

        self.http_service.service_response = make_response_mock
        self.http_service._get_current_route = Mock()
        self.http_service._get_current_route.return_value = self.http_v1_payload_route
        self.http_service._get_current_route.methods = []

        v1_event_mock.return_value = {}

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
        v1_event_mock.assert_called_with(
            flask_request=ANY,
            port=ANY,
            binary_types=ANY,
            stage_name=ANY,
            stage_variables=ANY,
            operation_name=None,
        )

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.construct_v1_event")
    @patch("samcli.local.apigw.local_apigw_service.construct_v2_event_http")
    def test_http_v2_payload_request_must_invoke_lambda(self, v2_event_mock, v1_event_mock, request_mock):
        make_response_mock = Mock()

        self.http_service.service_response = make_response_mock
        self.http_service._get_current_route = Mock()
        self.http_service._get_current_route.return_value = self.http_v2_payload_route
        self.http_service._get_current_route.methods = []

        v2_event_mock.return_value = {}

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
        v2_event_mock.assert_called_with(
            flask_request=ANY, port=ANY, binary_types=ANY, stage_name=ANY, stage_variables=ANY, route_key="test test"
        )

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._generate_lambda_event")
    def test_api_options_request_must_invoke_lambda(self, generate_mock, request_mock):
        generate_mock.return_value = {}
        make_response_mock = Mock()

        self.api_service.service_response = make_response_mock
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value.methods = ["OPTIONS"]
        self.api_service._get_current_route.return_value.payload_format_version = "1.0"
        self.api_service._get_current_route.return_value.authorizer_object = None

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
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._generate_lambda_event")
    def test_http_options_request_must_invoke_lambda(self, generate_mock, request_mock):
        generate_mock.return_value = {}
        make_response_mock = Mock()

        self.http_service.service_response = make_response_mock
        self.http_service._get_current_route = MagicMock()
        self.http_service._get_current_route.return_value.methods = ["OPTIONS"]
        self.http_service._get_current_route.return_value.payload_format_version = "1.0"
        self.http_service._get_current_route.return_value.authorizer_object = None

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
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._generate_lambda_event")
    def test_request_handler_returns_process_stdout_when_making_response(
        self, generate_mock, lambda_output_parser_mock, request_mock
    ):
        generate_mock.return_value = {}
        make_response_mock = Mock()
        request_mock.return_value = ("test", "test")
        self.api_service.service_response = make_response_mock
        current_route = Mock()
        current_route.payload_format_version = "2.0"
        current_route.authorizer_object = None
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value = current_route
        current_route.methods = []
        current_route.event_type = Route.API

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", Headers({"headers": "headers"}), "body")
        self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

        lambda_response = "response"
        is_customer_error = False
        lambda_output_parser_mock.get_lambda_output.return_value = lambda_response, is_customer_error
        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.api_service.service_response = service_response_mock

        result = self.api_service._request_handler()

        self.assertEqual(result, make_response_mock)
        lambda_output_parser_mock.get_lambda_output.assert_called_with(ANY)

        # Make sure the parse method is called only on the returned response and not on the raw data from stdout
        parse_output_mock.assert_called_with(lambda_response, ANY, ANY, Route.API)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._generate_lambda_event")
    def test_request_handler_returns_make_response(self, generate_mock, request_mock):
        generate_mock.return_value = {}
        make_response_mock = Mock()

        self.api_service.service_response = make_response_mock
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "1.0"
        self.api_service._get_current_route.return_value.authorizer_object = None

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
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._generate_lambda_event")
    def test_request_handles_error_when_invoke_cant_find_function(
        self, generate_mock, service_error_responses_patch, request_mock
    ):
        generate_mock.return_value = {}
        not_found_response_mock = Mock()
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value.payload_format_version = "2.0"
        self.api_service._get_current_route.return_value.authorizer_object = None
        self.api_service._get_current_route.methods = []

        service_error_responses_patch.lambda_not_found_response.return_value = not_found_response_mock

        self.lambda_runner.invoke.side_effect = FunctionNotFound()
        request_mock.return_value = ("test", "test")
        response = self.api_service._request_handler()

        self.assertEqual(response, not_found_response_mock)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._generate_lambda_event")
    def test_request_handles_error_when_invoke_function_with_inline_code(
        self, generate_mock, service_error_responses_patch, request_mock
    ):
        generate_mock.return_value = {}
        not_implemented_response_mock = Mock()
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value.payload_format_version = "2.0"
        self.api_service._get_current_route.return_value.authorizer_object = None
        self.api_service._get_current_route.methods = []

        service_error_responses_patch.not_implemented_locally.return_value = not_implemented_response_mock

        self.lambda_runner.invoke.side_effect = UnsupportedInlineCodeError(message="Inline code is not supported")
        request_mock.return_value = ("test", "test")
        response = self.api_service._request_handler()

        self.assertEqual(response, not_implemented_response_mock)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    def test_request_throws_when_invoke_fails(self, request_mock):
        self.lambda_runner.invoke.side_effect = Exception()

        self.api_service._get_current_route = Mock()
        request_mock.return_value = ("test", "test")

        with self.assertRaises(Exception):
            self.api_service._request_handler()

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._generate_lambda_event")
    def test_request_handler_errors_when_parse_lambda_output_raises_keyerror(
        self, generate_mock, service_error_responses_patch, request_mock
    ):
        generate_mock.return_value = {}
        parse_output_mock = Mock()
        parse_output_mock.side_effect = LambdaResponseParseException()
        self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

        failure_response_mock = Mock()

        service_error_responses_patch.lambda_failure_response.return_value = failure_response_mock

        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "1.0"
        self.api_service._get_current_route.return_value.authorizer_object = None

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
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._generate_lambda_event")
    def test_request_handler_errors_when_unable_to_read_binary_data(
        self, generate_mock, service_error_responses_patch, request_mock
    ):
        generate_mock.return_value = {}
        _construct_event = Mock()
        _construct_event.side_effect = UnicodeDecodeError("utf8", b"obj", 1, 2, "reason")
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "1.0"
        self.api_service._get_current_route.return_value.authorizer_object = None

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

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._valid_identity_sources")
    def test_request_contains_lambda_auth_missing_identity_sources(
        self, validate_id_mock, service_error_mock, request_mock
    ):
        route = self.api_gateway_route
        route.authorizer_object = LambdaAuthorizer("", "", "", [], "")

        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value = route
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "2.0"

        mocked_missing_lambda_auth_id = Mock()
        service_error_mock.missing_lambda_auth_identity_sources.return_value = mocked_missing_lambda_auth_id

        request_mock.return_value = ("test", "test")

        validate_id_mock.return_value = False

        result = self.api_service._request_handler()

        self.assertEqual(result, mocked_missing_lambda_auth_id)

    def test_valid_identity_sources_not_lambda_auth(self):
        route = self.api_gateway_route
        route.authorizer_object = None

        self.assertFalse(self.api_service._valid_identity_sources(Mock(), route))

    @parameterized.expand(
        [
            (True,),
            (False,),
        ]
    )
    @patch("samcli.local.apigw.authorizers.lambda_authorizer.LambdaAuthorizer._parse_identity_sources")
    @patch("samcli.local.apigw.authorizers.lambda_authorizer.LambdaAuthorizer.identity_sources")
    @patch("samcli.local.apigw.path_converter.PathConverter.convert_path_to_api_gateway")
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._build_v2_context")
    @patch("samcli.local.apigw.local_apigw_service.LocalApigwService._build_v1_context")
    def test_valid_identity_sources_id_source(
        self, is_valid, v1_mock, v2_mock, path_convert_mock, id_source_prop_mock, lambda_auth_parse_mock
    ):
        route = self.api_gateway_route
        route.authorizer_object = LambdaAuthorizer("", "", "", [], "")

        mocked_id_source_obj = Mock()
        mocked_id_source_obj.is_valid = Mock(return_value=is_valid)
        route.authorizer_object.identity_sources = [mocked_id_source_obj]

        self.assertEqual(self.api_service._valid_identity_sources(Mock(), route), is_valid)

    def test_create_method_arn(self):
        flask_request = Mock()
        flask_request.method = "GET"
        flask_request.path = "/endpoint"

        expected_method_arn = "arn:aws:execute-api:us-east-1:123456789012:1234567890/None/GET/endpoint"

        self.assertEqual(self.api_service._create_method_arn(flask_request, Route.API), expected_method_arn)

    @patch.object(LocalApigwService, "_create_method_arn")
    def test_generate_lambda_token_authorizer_event_invalid_identity_source(self, method_arn_mock):
        method_arn_mock.return_value = "arn"

        authorizer_object = LambdaAuthorizer("", "", "", [], "")
        authorizer_object.identity_sources = []

        with self.assertRaises(InvalidSecurityDefinition):
            self.api_service._generate_lambda_token_authorizer_event(Mock(), self.api_gateway_route, authorizer_object)

    @patch.object(LocalApigwService, "_create_method_arn")
    def test_generate_lambda_token_authorizer_event(self, method_arn_mock):
        method_arn_mock.return_value = "arn"

        authorizer_object = LambdaAuthorizer("", "", "", [], "")
        mocked_id_source_obj = Mock()
        mocked_id_source_obj.find_identity_value = Mock(return_value="123")
        authorizer_object._identity_sources = [mocked_id_source_obj]

        result = self.api_service._generate_lambda_token_authorizer_event(
            Mock(), self.api_gateway_route, authorizer_object
        )

        self.assertEqual(
            result,
            {
                "type": "TOKEN",
                "authorizationToken": "123",
                "methodArn": "arn",
            },
        )

    @parameterized.expand(
        [
            (
                LambdaAuthorizer.PAYLOAD_V2,
                ["value1", "value2"],
                "arn",
                {"identitySource": ["value1", "value2"], "routeArn": "arn"},
            ),
            (
                LambdaAuthorizer.PAYLOAD_V1,
                ["value1", "value2"],
                "arn",
                {
                    "identitySource": "value1,value2",
                    "authorizationToken": "value1,value2",
                    "methodArn": "arn",
                },
            ),
        ]
    )
    def test_generate_lambda_request_authorizer_event_http(self, payload, id_values, arn, expected_output):
        result = self.api_service._generate_lambda_request_authorizer_event_http(payload, id_values, arn)

        self.assertEqual(result, expected_output)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch.object(LocalApigwService, "_create_method_arn")
    @patch.object(LocalApigwService, "_generate_lambda_event")
    @patch.object(LocalApigwService, "_build_v1_context")
    @patch.object(LocalApigwService, "_build_v2_context")
    @patch.object(LocalApigwService, "_generate_lambda_request_authorizer_event_http")
    def test_generate_lambda_request_authorizer_event_http_request(
        self,
        generate_lambda_auth_http_mock,
        build_v2_mock,
        build_v1_mock,
        generate_lambda_mock,
        method_arn_mock,
        method_endpoints_mock,
    ):
        original = {"existing": "value"}
        payload_version = "2.0"
        method_arn = "arn"

        method_arn_mock.return_value = method_arn
        method_endpoints_mock.return_value = ("method", "endpoint")
        generate_lambda_mock.return_value = original
        build_v2_mock.return_value = {}
        build_v1_mock.return_value = {}

        authorizer_object = LambdaAuthorizer("", "", "", [], payload_version)
        mocked_id_source_obj = Mock()
        mocked_id_source_obj.find_identity_value = Mock(return_value="123")
        mocked_id_source_obj2 = Mock()
        mocked_id_source_obj2.find_identity_value = Mock(return_value="abc")
        authorizer_object._identity_sources = [mocked_id_source_obj, mocked_id_source_obj2]

        self.api_service._generate_lambda_request_authorizer_event(Mock(), self.http_gateway_route, authorizer_object)

        generate_lambda_auth_http_mock.assert_called_with(payload_version, ["123", "abc"], method_arn)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch.object(LocalApigwService, "_create_method_arn")
    @patch.object(LocalApigwService, "_generate_lambda_event")
    @patch.object(LocalApigwService, "_build_v1_context")
    @patch.object(LocalApigwService, "_build_v2_context")
    @patch.object(LocalApigwService, "_generate_lambda_request_authorizer_event_http")
    def test_generate_lambda_request_authorizer_event_api(
        self,
        generate_lambda_auth_http_mock,
        build_v2_mock,
        build_v1_mock,
        generate_lambda_mock,
        method_arn_mock,
        method_endpoints_mock,
    ):
        payload_version = "1.0"
        method_arn = "arn"
        original = {"existing": "value"}

        method_arn_mock.return_value = method_arn
        method_endpoints_mock.return_value = ("method", "endpoint")
        generate_lambda_mock.return_value = original
        build_v2_mock.return_value = {}
        build_v1_mock.return_value = {}

        authorizer_object = LambdaAuthorizer("", "", "", [], payload_version)

        result = self.api_service._generate_lambda_request_authorizer_event(
            Mock(), self.api_gateway_route, authorizer_object
        )

        original.update({"methodArn": method_arn, "type": "REQUEST"})

        self.assertEqual(result, original)
        generate_lambda_auth_http_mock.assert_not_called()

    @patch.object(LocalApigwService, "_generate_lambda_token_authorizer_event")
    @patch.object(LocalApigwService, "_generate_lambda_request_authorizer_event")
    def test_generate_lambda_authorizer_event_token(self, request_mock, token_mock):
        token_auth = LambdaAuthorizer(Mock(), LambdaAuthorizer.TOKEN, Mock(), [], Mock())

        token_mock.return_value = {}
        request_mock.return_value = {}

        self.api_service._generate_lambda_authorizer_event(Mock(), Mock(), token_auth)
        token_mock.assert_called()
        request_mock.assert_not_called()

    @patch.object(LocalApigwService, "_generate_lambda_token_authorizer_event")
    @patch.object(LocalApigwService, "_generate_lambda_request_authorizer_event")
    def test_generate_lambda_authorizer_event_request(self, request_mock, token_mock):
        request_auth = LambdaAuthorizer(Mock(), LambdaAuthorizer.REQUEST, Mock(), [], Mock())

        token_mock.return_value = {}
        request_mock.return_value = {}

        self.api_service._generate_lambda_authorizer_event(Mock(), Mock(), request_auth)
        token_mock.assert_not_called()
        request_mock.assert_called()

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch.object(LocalApigwService, "_generate_lambda_authorizer_event")
    @patch.object(LocalApigwService, "_valid_identity_sources")
    @patch.object(LocalApigwService, "_invoke_lambda_function")
    @patch.object(LocalApigwService, "_invoke_parse_lambda_authorizer")
    @patch.object(EventTracker, "track_event")
    @patch("samcli.local.apigw.local_apigw_service.construct_v1_event")
    @patch("samcli.local.apigw.local_apigw_service.construct_v2_event_http")
    def test_lambda_auth_called(
        self,
        v2_event_mock,
        v1_event_mock,
        track_mock,
        lambda_invoke_mock,
        invoke_mock,
        validate_id_mock,
        gen_auth_event_mock,
        request_mock,
    ):
        make_response_mock = Mock()
        validate_id_mock.return_value = True

        # create mock authorizer
        auth = LambdaAuthorizer(Mock(), Mock(), "auth_lambda", [], Mock(), Mock(), Mock())
        auth.is_valid_response = Mock(return_value=True)
        auth.get_context = Mock(return_value={})
        self.api_gateway_route.authorizer_object = auth

        # get api service to return mocked route containing authorizer
        self.api_service.service_response = make_response_mock
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value = self.api_gateway_route
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "2.0"
        v1_event_mock.return_value = {}

        parse_output_mock = Mock(return_value=("status_code", Headers({"headers": "headers"}), "body"))
        self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

        service_response_mock = Mock(return_value=make_response_mock)
        self.api_service.service_response = service_response_mock

        request_mock.return_value = ("test", "test")

        self.api_service._request_handler()

        # successful invoke
        self.api_service._invoke_parse_lambda_authorizer.assert_called_with(auth, ANY, ANY, self.api_gateway_route)

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch.object(LocalApigwService, "_generate_lambda_authorizer_event")
    @patch.object(LocalApigwService, "_valid_identity_sources")
    @patch.object(LocalApigwService, "_invoke_lambda_function")
    @patch.object(LocalApigwService, "_invoke_parse_lambda_authorizer")
    @patch.object(EventTracker, "track_event")
    @patch("samcli.local.apigw.local_apigw_service.construct_v1_event")
    @patch("samcli.local.apigw.local_apigw_service.construct_v2_event_http")
    @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    def test_lambda_invoke_track_event_exception(
        self,
        service_mock,
        v2_event_mock,
        v1_event_mock,
        track_mock,
        lambda_invoke_mock,
        invoke_mock,
        validate_id_mock,
        gen_auth_event_mock,
        request_mock,
    ):
        make_response_mock = Mock()
        validate_id_mock.return_value = True

        # create mock authorizer
        auth = LambdaAuthorizer(Mock(), Mock(), "auth_lambda", [], Mock(), Mock(), Mock())
        auth.is_valid_response = Mock(return_value=True)
        auth.get_context = Mock(return_value={})
        self.api_gateway_route.authorizer_object = auth

        # get api service to return mocked route containing authorizer
        self.api_service.service_response = make_response_mock
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value = self.api_gateway_route
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "2.0"
        v1_event_mock.return_value = {}

        parse_output_mock = Mock(return_value=("status_code", Headers({"headers": "headers"}), "body"))
        self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

        service_response_mock = Mock(return_value=make_response_mock)
        self.api_service.service_response = service_response_mock

        request_mock.return_value = ("test", "test")

        lambda_invoke_mock.side_effect = AuthorizerUnauthorizedRequest("msg")
        service_mock.lambda_authorizer_unauthorized = Mock()

        self.api_service._request_handler()

        track_mock.assert_called_with(
            event_name=EventName.USED_FEATURE.value,
            event_value=UsedFeature.INVOKED_CUSTOM_LAMBDA_AUTHORIZERS.value,
            session_id=ANY,
            exception_name=AuthorizerUnauthorizedRequest.__name__,
        )

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch.object(LocalApigwService, "_create_method_arn")
    @patch.object(LocalApigwService, "_generate_lambda_authorizer_event")
    @patch.object(LocalApigwService, "_valid_identity_sources")
    @patch.object(LocalApigwService, "_invoke_lambda_function")
    @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    @patch("samcli.local.apigw.local_apigw_service.construct_v1_event")
    @patch("samcli.local.apigw.local_apigw_service.construct_v2_event_http")
    def test_lambda_auth_unauthorized_response(
        self,
        v2_event_mock,
        v1_event_mock,
        service_err_mock,
        invoke_mock,
        validate_id_mock,
        gen_auth_event_mock,
        method_arn_mock,
        request_mock,
    ):
        make_response_mock = Mock()
        validate_id_mock.return_value = True

        # create mock authorizer
        auth = LambdaAuthorizer(Mock(), Mock(), "auth_lambda", [], Mock(), Mock(), Mock())
        auth.is_valid_response = Mock(return_value=False)
        self.api_gateway_route.authorizer_object = auth

        # get api service to return mocked route containing authorizer
        self.api_service.service_response = make_response_mock
        self.api_service._get_current_route = MagicMock()
        self.api_service._get_current_route.return_value = self.api_gateway_route
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "2.0"
        v1_event_mock.return_value = {}

        parse_output_mock = Mock(return_value=("status_code", Headers({"headers": "headers"}), "body"))
        self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

        service_response_mock = Mock(return_value=make_response_mock)
        self.api_service.service_response = service_response_mock

        request_mock.return_value = ("test", "test")
        method_arn_mock.return_value = "arn"

        mock_context = {"key": "value"}
        invoke_mock.side_effect = [{"context": mock_context}, Mock()]

        unauth_mock = Mock()
        service_err_mock.lambda_authorizer_unauthorized.return_value = unauth_mock

        result = self.api_service._request_handler()

        self.assertEqual(result, unauth_mock)

    @patch.object(LocalApigwService, "_invoke_lambda_function")
    @patch.object(LocalApigwService, "_create_method_arn")
    @patch.object(EventTracker, "track_event")
    def test_lambda_authorizer_pass_context_http(self, event_mock, method_arn_mock, mock_invoke):
        mock_get_context = Mock()
        route_event = {}

        auth = LambdaAuthorizer(Mock(), Mock(), "auth_lambda", [], Mock(), Mock(), Mock())
        auth.is_valid_response = Mock(return_value=True)
        auth.get_context = Mock(return_value=mock_get_context)
        self.http_v2_payload_route.authorizer_object = auth

        self.http_service._invoke_parse_lambda_authorizer(auth, {}, route_event, self.http_v2_payload_route)
        self.assertEqual(route_event, {"requestContext": {"authorizer": {"lambda": mock_get_context}}})

    @patch.object(LocalApigwService, "_invoke_lambda_function")
    @patch.object(LocalApigwService, "_create_method_arn")
    @patch.object(EventTracker, "track_event")
    def test_lambda_authorizer_pass_context_api(self, event_mock, method_arn_mock, mock_invoke):
        mock_get_context = Mock()
        route_event = {}

        auth = LambdaAuthorizer(Mock(), Mock(), "auth_lambda", [], Mock(), Mock(), Mock())
        auth.is_valid_response = Mock(return_value=True)
        auth.get_context = Mock(return_value=mock_get_context)
        self.api_gateway_route.authorizer_object = auth

        self.api_service._invoke_parse_lambda_authorizer(auth, {}, route_event, self.api_gateway_route)
        self.assertEqual(route_event, {"requestContext": {"authorizer": mock_get_context}})

    @patch.object(LocalApigwService, "get_request_methods_endpoints")
    @patch.object(LocalApigwService, "_valid_identity_sources")
    @patch.object(LocalApigwService, "_generate_lambda_authorizer_event")
    @patch.object(LocalApigwService, "_invoke_parse_lambda_authorizer")
    @patch("samcli.local.apigw.local_apigw_service.construct_v1_event")
    @patch("samcli.local.apigw.local_apigw_service.construct_v2_event_http")
    def test_authorizer_function_not_found_invokes_endpoint(
        self,
        v2_event_mock,
        v1_event_mock,
        invoke_lambda_auth_mock,
        lambda_auth_event_mock,
        id_source_mock,
        request_mock,
    ):
        make_response_mock = Mock()

        # mock lambda auth invoke method to raise FunctionNotFound
        invoke_lambda_auth_mock.side_effect = [FunctionNotFound()]

        # mock the route with fake lambda authorizer
        self.api_service.service_response = make_response_mock
        self.api_service._get_current_route = MagicMock()

        self.api_gateway_route.authorizer_object = Mock()

        self.api_service._get_current_route.return_value = self.api_gateway_route
        self.api_service._get_current_route.methods = []
        self.api_service._get_current_route.return_value.payload_format_version = "2.0"
        v1_event_mock.return_value = {}

        # mock the route response parser
        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", Headers({"headers": "headers"}), "body")
        self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

        # mock the response creator
        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.api_service.service_response = service_response_mock

        request_mock.return_value = ("test", "test")

        result = self.api_service._request_handler()

        # validate route lambda still invoked after Lambda auth function not found
        self.assertEqual(result, make_response_mock)
        self.lambda_runner.invoke.assert_called_with(
            self.api_gateway_route.function_name, ANY, stdout=ANY, stderr=self.stderr
        )


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


class TestService_cors_response_headers(TestCase):
    def test_response_cors_no_origin(self):
        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = []
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        cors = Cors(allow_origin="*", allow_methods="GET,POST,OPTIONS")

        response_cors_headers = Cors.cors_to_headers(cors)
        response_cors_headers = LocalApigwService._response_cors_headers(request_mock, response_cors_headers)

        self.assertTrue("Access-Control-Allow-Origin" not in response_cors_headers)

    def test_response_cors_with_origin(self):
        incoming_origin = "localhost:3000"

        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = []
        headers_mock.keys.return_value = ["Origin", "Content-Type"]
        headers_mock.get.side_effect = [incoming_origin, "application/json"]
        headers_mock.getlist.side_effect = [[incoming_origin], ["application/json"]]
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        cors = Cors(allow_origin="*", allow_methods="GET,POST,OPTIONS", allow_credentials=True)

        response_cors_headers = Cors.cors_to_headers(cors)
        response_cors_headers = LocalApigwService._response_cors_headers(request_mock, response_cors_headers)

        self.assertEqual(incoming_origin, response_cors_headers["Access-Control-Allow-Origin"])

    def test_response_cors_with_origin_single_domain(self):
        incoming_origin = "localhost:3000"

        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = []
        headers_mock.keys.return_value = ["Origin", "Content-Type"]
        headers_mock.get.side_effect = [incoming_origin, "application/json"]
        headers_mock.getlist.side_effect = [[incoming_origin], ["application/json"]]
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        cors = Cors(allow_origin="localhost:3000", allow_methods="GET,POST,OPTIONS", allow_credentials=True)

        response_cors_headers = Cors.cors_to_headers(cors)
        response_cors_headers = LocalApigwService._response_cors_headers(request_mock, response_cors_headers)

        self.assertEqual(incoming_origin, response_cors_headers["Access-Control-Allow-Origin"])

    def test_response_cors_with_origin_multi_domains(self):
        incoming_origin = "localhost:3000"

        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = []
        headers_mock.keys.return_value = ["Origin", "Content-Type"]
        headers_mock.get.side_effect = [incoming_origin, "application/json"]
        headers_mock.getlist.side_effect = [[incoming_origin], ["application/json"]]
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        cors = Cors(
            allow_origin="localhost:3000,localhost:6000", allow_methods="GET,POST,OPTIONS", allow_credentials=True
        )

        response_cors_headers = Cors.cors_to_headers(cors)
        response_cors_headers = LocalApigwService._response_cors_headers(request_mock, response_cors_headers)

        self.assertEqual(incoming_origin, response_cors_headers["Access-Control-Allow-Origin"])

    def test_response_cors_with_origin_multi_domains_not_matching(self):
        incoming_origin = "localhost:3000"

        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = []
        headers_mock.keys.return_value = ["Origin", "Content-Type"]
        headers_mock.get.side_effect = [incoming_origin, "application/json"]
        headers_mock.getlist.side_effect = [[incoming_origin], ["application/json"]]
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        cors = Cors(
            allow_origin="localhost:4000,localhost:6000", allow_methods="GET,POST,OPTIONS", allow_credentials=True
        )

        response_cors_headers = Cors.cors_to_headers(cors)
        response_cors_headers = LocalApigwService._response_cors_headers(request_mock, response_cors_headers)

        self.assertTrue("Access-Control-Allow-Origin" not in response_cors_headers)

    def test_response_cors_not_allow_credentials(self):
        incoming_origin = "localhost:3000"

        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = []
        headers_mock.keys.return_value = ["Origin", "Content-Type"]
        headers_mock.get.side_effect = [incoming_origin, "application/json"]
        headers_mock.getlist.side_effect = [[incoming_origin], ["application/json"]]
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        cors = Cors(allow_origin="*", allow_methods="GET,POST,OPTIONS", allow_credentials=False)

        response_cors_headers = Cors.cors_to_headers(cors)
        response_cors_headers = LocalApigwService._response_cors_headers(request_mock, response_cors_headers)

        self.assertTrue("Access-Control-Allow-Origin" not in response_cors_headers)

    def test_response_cors_missing_allow_credentials(self):
        incoming_origin = "localhost:3000"

        request_mock = Mock()
        headers_mock = Mock()
        headers_mock.keys.return_value = []
        headers_mock.keys.return_value = ["Origin", "Content-Type"]
        headers_mock.get.side_effect = [incoming_origin, "application/json"]
        headers_mock.getlist.side_effect = [[incoming_origin], ["application/json"]]
        request_mock.headers = headers_mock
        request_mock.scheme = "http"

        cors = Cors(allow_origin="*", allow_methods="GET,POST,OPTIONS")

        response_cors_headers = Cors.cors_to_headers(cors)
        response_cors_headers = LocalApigwService._response_cors_headers(request_mock, response_cors_headers)

        self.assertTrue("Access-Control-Allow-Origin" not in response_cors_headers)


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
        self.assertEqual(path, output)

    def test_path_converter_to_python_accepts_any_path(self):
        map = Mock()
        map.charset = "utf-8"
        path_converter = CatchAllPathConverter(map)
        path = "/path/test/sub_path"
        output = path_converter.to_python(path)
        self.assertEqual(path, output)

    def test_path_converter_matches_any_path(self):
        map = Mock()
        map.charset = "utf-8"
        path_converter = CatchAllPathConverter(map)
        path = "/path/test/sub_path"
        self.assertRegex(path, path_converter.regex)
