import base64
import copy
import json
from datetime import datetime
from unittest import TestCase

from unittest.mock import Mock, patch, ANY, MagicMock
from parameterized import parameterized, param
from werkzeug.datastructures import Headers
from graphql import GraphQLResolveInfo

from samcli.lib.providers.provider import GraphQLApi
from samcli.local.appsync.local_appsync_service import LocalAppSyncService, Resolver
from samcli.local.lambdafn.exceptions import FunctionNotFound


class TestApiGatewayService(TestCase):
    def setUp(self):
        self.function_name = Mock()
        self.appsync_resolver = Resolver(function_name=self.function_name, object_type="query", field_name="foo_bar")
        self.api_list_of_resolvers = [self.appsync_resolver]

        self.lambda_runner = Mock()
        self.lambda_runner.is_debugging.return_value = False

        self.stderr = Mock()
        self.api = GraphQLApi(resolvers=[self.appsync_resolver])
        self.api_service = LocalAppSyncService(
            self.api, self.lambda_runner, port=3000, host="127.0.0.1", stderr=self.stderr
        )

    @patch("samcli.local.appsync.local_appsync_service.make_executable_schema")
    @patch("samcli.local.appsync.local_appsync_service.load_schema_from_path")
    @patch("samcli.local.appsync.local_appsync_service.Flask")
    def test_create_creates_flask_app_with_url_rules(self, flask, load_schema_from_path, make_exec_schema):
        app_mock = MagicMock()
        app_mock.config = {}
        flask.return_value = app_mock

        self.api_service._construct_error_handling = Mock()

        self.api_service.create()

        app_mock.add_url_rule.assert_called_once_with(
            "/graphql",
            endpoint="/graphql",
            view_func=self.api_service._request_handler,
            methods=["GET", "POST"],
            provide_automatic_options=False,
        )

    def test_api_initalize_creates_default_values(self):
        self.assertEqual(self.api_service.port, 3000)
        self.assertEqual(self.api_service.host, "127.0.0.1")
        self.assertEqual(self.api_service.api.resolvers, self.api_list_of_resolvers)
        self.assertIsNone(self.api_service.static_dir)
        self.assertEqual(self.api_service.lambda_runner, self.lambda_runner)

    def test_initalize_with_values(self):
        lambda_runner = Mock()
        local_service = LocalAppSyncService(
            GraphQLApi(), lambda_runner, static_dir="dir/static", port=5000, host="129.0.0.0"
        )
        self.assertEqual(local_service.port, 5000)
        self.assertEqual(local_service.host, "129.0.0.0")
        self.assertEqual(local_service.api.resolvers, [])
        self.assertEqual(local_service.static_dir, "dir/static")
        self.assertEqual(local_service.lambda_runner, lambda_runner)

    @patch.object(LocalAppSyncService, "_direct_lambda_resolver_event")
    @patch("samcli.local.appsync.local_appsync_service.LambdaOutputParser")
    def test_generate_resolver_fn(self, lambda_output_parser, direct_lambda_resolver_event):
        test_object = {"foo": "bar"}
        mock_logs_string = "some logs"
        mock_lambda_output_json = json.dumps(test_object)
        lambda_output_parser.get_lambda_output.return_value = (mock_lambda_output_json, mock_logs_string, None)

        stderr_mock = Mock()
        lambda_runner = Mock()
        direct_lambda_resolver_event = Mock()
        resolver = Resolver("foo", "bar", "foo_bar_field_name")

        local_service = LocalAppSyncService(GraphQLApi(), lambda_runner, stderr=stderr_mock)
        resolver_fn = local_service._generate_resolver_fn(resolver)

        info = MagicMock()
        result = resolver_fn(None, info)

        self.assertEqual(result, test_object)
        stderr_mock.write.assert_called_once_with(mock_logs_string)

    # def test_request_handles_error_when_invoke_cant_find_function(self, service_error_responses_patch, request_mock):
    #     not_found_response_mock = Mock()
    #     self.api_service._construct_v_1_0_event = Mock()
    #     self.api_service._get_current_route = MagicMock()
    #     self.api_service._get_current_route.methods = []

    #     service_error_responses_patch.lambda_not_found_response.return_value = not_found_response_mock

    #     self.lambda_runner.invoke.side_effect = FunctionNotFound()
    #     request_mock.return_value = ("test", "test")
    #     response = self.api_service._request_handler()

    #     self.assertEqual(response, not_found_response_mock)

    # @patch.object(LocalApigwService, "get_request_methods_endpoints")
    # @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    # def test_request_handles_error_when_invoke_cant_find_function(self, service_error_responses_patch, request_mock):
    #     not_found_response_mock = Mock()
    #     self.api_service._construct_v_1_0_event = Mock()
    #     self.api_service._get_current_route = MagicMock()
    #     self.api_service._get_current_route.methods = []

    #     service_error_responses_patch.lambda_not_found_response.return_value = not_found_response_mock

    #     self.lambda_runner.invoke.side_effect = FunctionNotFound()
    #     request_mock.return_value = ("test", "test")
    #     response = self.api_service._request_handler()

    #     self.assertEqual(response, not_found_response_mock)

    # @patch.object(LocalApigwService, "get_request_methods_endpoints")
    # def test_request_throws_when_invoke_fails(self, request_mock):
    #     self.lambda_runner.invoke.side_effect = Exception()

    #     self.api_service._construct_v_1_0_event = Mock()
    #     self.api_service._get_current_route = Mock()
    #     request_mock.return_value = ("test", "test")

    #     with self.assertRaises(Exception):
    #         self.api_service._request_handler()

    # @patch.object(LocalApigwService, "get_request_methods_endpoints")
    # @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    # def test_request_handler_errors_when_parse_lambda_output_raises_keyerror(
    #     self, service_error_responses_patch, request_mock
    # ):
    #     parse_output_mock = Mock()
    #     parse_output_mock.side_effect = LambdaResponseParseException()
    #     self.api_service._parse_v1_payload_format_lambda_output = parse_output_mock

    #     failure_response_mock = Mock()

    #     service_error_responses_patch.lambda_failure_response.return_value = failure_response_mock

    #     self.api_service._construct_v_1_0_event = Mock()
    #     self.api_service._get_current_route = MagicMock()
    #     self.api_service._get_current_route.methods = []

    #     request_mock.return_value = ("test", "test")
    #     result = self.api_service._request_handler()

    #     self.assertEqual(result, failure_response_mock)

    # @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    # def test_request_handler_errors_when_get_current_route_fails(self, service_error_responses_patch):
    #     get_current_route = Mock()
    #     get_current_route.side_effect = KeyError()
    #     self.api_service._get_current_route = get_current_route

    #     with self.assertRaises(KeyError):
    #         self.api_service._request_handler()

    # @patch.object(LocalApigwService, "get_request_methods_endpoints")
    # @patch("samcli.local.apigw.local_apigw_service.ServiceErrorResponses")
    # def test_request_handler_errors_when_unable_to_read_binary_data(self, service_error_responses_patch, request_mock):
    #     _construct_event = Mock()
    #     _construct_event.side_effect = UnicodeDecodeError("utf8", b"obj", 1, 2, "reason")
    #     self.api_service._get_current_route = MagicMock()
    #     self.api_service._get_current_route.methods = []

    #     self.api_service._construct_v_1_0_event = _construct_event

    #     failure_mock = Mock()
    #     service_error_responses_patch.lambda_failure_response.return_value = failure_mock

    #     request_mock.return_value = ("test", "test")
    #     result = self.api_service._request_handler()
    #     self.assertEqual(result, failure_mock)

    # def test_get_current_route(self):
    #     request_mock = Mock()
    #     request_mock.return_value.endpoint = "path"
    #     request_mock.return_value.method = "method"

    #     route_key_method_mock = Mock()
    #     route_key_method_mock.return_value = "method:path"
    #     self.api_service._route_key = route_key_method_mock
    #     self.api_service._dict_of_routes = {"method:path": "function"}

    #     self.assertEqual(self.api_service._get_current_route(request_mock), "function")

    # def test_get_current_route_keyerror(self):
    #     """
    #     When the a HTTP request for given method+path combination is allowed by Flask but not in the list of routes,
    #     something is messed up. Flask should be configured only from the list of routes.
    #     """

    #     request_mock = Mock()
    #     request_mock.endpoint = "path"
    #     request_mock.method = "method"

    #     route_key_method_mock = Mock()
    #     route_key_method_mock.return_value = "method:path"
    #     self.api_service._route_key = route_key_method_mock
    #     self.api_service._dict_of_routes = {"a": "b"}

    #     with self.assertRaises(KeyError):
    #         self.api_service._get_current_route(request_mock)


class TestService_construct_direct_lambda_event(TestCase):
    def setUp(self):
        self.request_mock = Mock()
        self.request_mock.headers = {}
        self.request_mock.get_json.return_value = {"query": "QUERY_DATA_FOO_BAR"}
        self.info_mock = MagicMock()
        self.info_mock.field_name = "something"
        self.info_mock.parent_type.name = "something else"
        self.info_mock.variable_values = {}

        self.expected_dict = {
            "arguments": {},
            "identity": {},
            "info": {
                "fieldName": "something",
                "parentTypeName": "something else",
                "selectionSetGraphQL": "QUERY_DATA_FOO_BAR",
                "selectionSetList": [],
                "variables": {},
            },
            "request": {"headers": {}},
            "source": {},
        }

    def test_construct_event_no_data(self):
        actual_event_str = LocalAppSyncService._direct_lambda_resolver_event(
            self.request_mock, arguments={}, info=self.info_mock
        )
        actual_event_dict = json.loads(actual_event_str)
        self.assertEqual(actual_event_dict, self.expected_dict)

    def test_construct_event_arguments(self):
        arguments = {
            "foo1": "bar1",
            "bar2": "foo2",
        }
        actual_event_str = LocalAppSyncService._direct_lambda_resolver_event(
            self.request_mock, arguments=arguments, info=self.info_mock
        )
        actual_event_dict = json.loads(actual_event_str)
        expected = self.expected_dict
        expected["arguments"] = arguments
        self.assertEqual(actual_event_dict, self.expected_dict)

    def test_construct_event_selection_list(self):
        info_mock = self.info_mock

        field_name_one = MagicMock()
        field_name_one.name.value = "someField"
        field_name_two = MagicMock()
        field_name_two.name.value = "someOtherField"
        info_mock.field_nodes[0].selection_set.selections = [
            field_name_one,
            field_name_two,
        ]

        selection_set = [a for a in info_mock.field_nodes[0].selection_set.selections]
        print("Selection set %s", selection_set)

        actual_event_str = LocalAppSyncService._direct_lambda_resolver_event(
            self.request_mock, arguments={}, info=info_mock
        )
        actual_event_dict = json.loads(actual_event_str)
        expected = self.expected_dict
        expected["info"]["selectionSetList"] = ["someField", "someOtherField"]
        self.assertEqual(actual_event_dict, self.expected_dict)
