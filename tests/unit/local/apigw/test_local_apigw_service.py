from unittest import TestCase
from mock import Mock, patch, ANY
import json
import base64

from parameterized import parameterized, param

from samcli.local.apigw.local_apigw_service import LocalApigwService, Route
from samcli.local.lambdafn.exceptions import FunctionNotFound


class TestApiGatewayService(TestCase):

    def setUp(self):
        self.function_name = Mock()
        self.api_gateway_route = Route(['GET'], self.function_name, '/')
        self.list_of_routes = [self.api_gateway_route]

        self.lambda_runner = Mock()
        self.lambda_runner.is_debugging.return_value = False

        self.stderr = Mock()
        self.service = LocalApigwService(self.list_of_routes,
                                         self.lambda_runner,
                                         port=3000,
                                         host='127.0.0.1',
                                         stderr=self.stderr)

    def test_request_must_invoke_lambda(self):
        make_response_mock = Mock()

        self.service.service_response = make_response_mock
        self.service._get_current_route = Mock()
        self.service._construct_event = Mock()

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", "headers", "body")
        self.service._parse_lambda_output = parse_output_mock

        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.service.service_response = service_response_mock

        result = self.service._request_handler()

        self.assertEquals(result, make_response_mock)
        self.lambda_runner.invoke.assert_called_with(ANY,
                                                     ANY,
                                                     stdout=ANY,
                                                     stderr=self.stderr)

    @patch('samcli.local.apigw.local_apigw_service.LambdaOutputParser')
    def test_request_handler_returns_process_stdout_when_making_response(self, lambda_output_parser_mock):

        make_response_mock = Mock()

        self.service.service_response = make_response_mock
        self.service._get_current_route = Mock()
        self.service._construct_event = Mock()

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", "headers", "body")
        self.service._parse_lambda_output = parse_output_mock

        lambda_logs = "logs"
        lambda_response = "response"
        is_customer_error = False
        lambda_output_parser_mock.get_lambda_output.return_value = lambda_response, lambda_logs, is_customer_error
        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.service.service_response = service_response_mock

        result = self.service._request_handler()

        self.assertEquals(result, make_response_mock)
        lambda_output_parser_mock.get_lambda_output.assert_called_with(ANY)

        # Make sure the parse method is called only on the returned response and not on the raw data from stdout
        parse_output_mock.assert_called_with(lambda_response, ANY, ANY)
        # Make sure the logs are written to stderr
        self.stderr.write.assert_called_with(lambda_logs)

    def test_request_handler_returns_make_response(self):
        make_response_mock = Mock()

        self.service.service_response = make_response_mock
        self.service._get_current_route = Mock()
        self.service._construct_event = Mock()

        parse_output_mock = Mock()
        parse_output_mock.return_value = ("status_code", "headers", "body")
        self.service._parse_lambda_output = parse_output_mock

        service_response_mock = Mock()
        service_response_mock.return_value = make_response_mock
        self.service.service_response = service_response_mock

        result = self.service._request_handler()

        self.assertEquals(result, make_response_mock)

    def test_create_creates_dict_of_routes(self):
        function_name_1 = Mock()
        function_name_2 = Mock()
        api_gateway_route_1 = Route(['GET'], function_name_1, '/')
        api_gateway_route_2 = Route(['POST'], function_name_2, '/')

        list_of_routes = [api_gateway_route_1, api_gateway_route_2]

        lambda_runner = Mock()

        service = LocalApigwService(list_of_routes, lambda_runner)

        service.create()

        self.assertEquals(service._dict_of_routes, {'/:GET': api_gateway_route_1,
                                                    '/:POST': api_gateway_route_2
                                                    })

    @patch('samcli.local.apigw.local_apigw_service.Flask')
    def test_create_creates_flask_app_with_url_rules(self, flask):
        app_mock = Mock()
        flask.return_value = app_mock

        self.service._construct_error_handling = Mock()

        self.service.create()

        app_mock.add_url_rule.assert_called_once_with('/',
                                                      endpoint='/',
                                                      view_func=self.service._request_handler,
                                                      methods=['GET'],
                                                      provide_automatic_options=False)

    def test_initalize_creates_default_values(self):
        self.assertEquals(self.service.port, 3000)
        self.assertEquals(self.service.host, '127.0.0.1')
        self.assertEquals(self.service.routing_list, self.list_of_routes)
        self.assertIsNone(self.service.static_dir)
        self.assertEquals(self.service.lambda_runner, self.lambda_runner)

    def test_initalize_with_values(self):
        lambda_runner = Mock()
        local_service = LocalApigwService([], lambda_runner, static_dir='dir/static', port=5000, host='129.0.0.0')
        self.assertEquals(local_service.port, 5000)
        self.assertEquals(local_service.host, '129.0.0.0')
        self.assertEquals(local_service.routing_list, [])
        self.assertEquals(local_service.static_dir, 'dir/static')
        self.assertEquals(local_service.lambda_runner, lambda_runner)

    @patch('samcli.local.apigw.local_apigw_service.ServiceErrorResponses')
    def test_request_handles_error_when_invoke_cant_find_function(self, service_error_responses_patch):

        not_found_response_mock = Mock()
        self.service._construct_event = Mock()
        self.service._get_current_route = Mock()
        service_error_responses_patch.lambda_not_found_response.return_value = not_found_response_mock

        self.lambda_runner.invoke.side_effect = FunctionNotFound()

        response = self.service._request_handler()

        self.assertEquals(response, not_found_response_mock)

    def test_request_throws_when_invoke_fails(self):
        self.lambda_runner.invoke.side_effect = Exception()

        self.service._construct_event = Mock()
        self.service._get_current_route = Mock()

        with self.assertRaises(Exception):
            self.service._request_handler()

    @patch('samcli.local.apigw.local_apigw_service.ServiceErrorResponses')
    def test_request_handler_errors_when_parse_lambda_output_raises_keyerror(self, service_error_responses_patch):
        parse_output_mock = Mock()
        parse_output_mock.side_effect = KeyError()
        self.service._parse_lambda_output = parse_output_mock

        failure_response_mock = Mock()

        service_error_responses_patch.lambda_failure_response.return_value = failure_response_mock

        self.service._construct_event = Mock()
        self.service._get_current_route = Mock()

        result = self.service._request_handler()

        self.assertEquals(result, failure_response_mock)

    @patch('samcli.local.apigw.local_apigw_service.ServiceErrorResponses')
    def test_request_handler_errors_when_get_current_route_fails(self, service_error_responses_patch):
        get_current_route = Mock()
        get_current_route.side_effect = KeyError()
        self.service._get_current_route = get_current_route

        with self.assertRaises(KeyError):
            self.service._request_handler()

    @patch('samcli.local.apigw.local_apigw_service.ServiceErrorResponses')
    def test_request_handler_errors_when_unable_to_read_binary_data(self, service_error_responses_patch):
        _construct_event = Mock()
        _construct_event.side_effect = UnicodeDecodeError("utf8", b"obj", 1, 2, "reason")
        self.service._get_current_route = Mock()
        self.service._construct_event = _construct_event

        failure_mock = Mock()
        service_error_responses_patch.lambda_failure_response.return_value = failure_mock

        result = self.service._request_handler()
        self.assertEquals(result, failure_mock)

    @patch('samcli.local.apigw.local_apigw_service.request')
    def test_get_current_route(self, request_patch):

        request_mock = Mock()
        request_mock.endpoint = "path"
        request_mock.method = "method"

        request_patch.return_value = request_mock

        route_key_method_mock = Mock()
        route_key_method_mock.return_value = "method:path"
        self.service._route_key = route_key_method_mock
        self.service._dict_of_routes = {"method:path": "function"}

        self.assertEquals(self.service._get_current_route(request_mock), "function")

    @patch('samcli.local.apigw.local_apigw_service.request')
    def test_get_current_route_keyerror(self, request_patch):
        """
        When the a HTTP request for given method+path combination is allowed by Flask but not in the list of routes,
        something is messed up. Flask should be configured only from the list of routes.
        """

        request_mock = Mock()
        request_mock.endpoint = "path"
        request_mock.method = "method"

        request_patch.return_value = request_mock

        route_key_method_mock = Mock()
        route_key_method_mock.return_value = "method:path"
        self.service._route_key = route_key_method_mock
        self.service._dict_of_routes = {"a": "b"}

        with self.assertRaises(KeyError):
            self.service._get_current_route(request_mock)


class TestApiGatewayModel(TestCase):

    def setUp(self):
        self.function_name = "name"
        self.api_gateway = Route(['POST'], self.function_name, '/')

    def test_class_initialization(self):
        self.assertEquals(self.api_gateway.methods, ['POST'])
        self.assertEquals(self.api_gateway.function_name, self.function_name)
        self.assertEquals(self.api_gateway.path, '/')


class TestServiceParsingLambdaOutput(TestCase):

    def test_default_content_type_header_added_with_no_headers(self):
        lambda_output = '{"statusCode": 200, "body": "{\\"message\\":\\"Hello from Lambda\\"}", ' \
                        '"isBase64Encoded": false}'

        (_, headers, _) = LocalApigwService._parse_lambda_output(lambda_output, binary_types=[], flask_request=Mock())

        self.assertIn("Content-Type", headers)
        self.assertEquals(headers["Content-Type"], "application/json")

    def test_default_content_type_header_added_with_empty_headers(self):
        lambda_output = '{"statusCode": 200, "headers":{}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", ' \
                        '"isBase64Encoded": false}'

        (_, headers, _) = LocalApigwService._parse_lambda_output(lambda_output, binary_types=[], flask_request=Mock())

        self.assertIn("Content-Type", headers)
        self.assertEquals(headers["Content-Type"], "application/json")

    def test_custom_content_type_header_is_not_modified(self):
        lambda_output = '{"statusCode": 200, "headers":{"Content-Type": "text/xml"}, "body": "{}", ' \
                        '"isBase64Encoded": false}'

        (_, headers, _) = LocalApigwService._parse_lambda_output(lambda_output, binary_types=[], flask_request=Mock())

        self.assertIn("Content-Type", headers)
        self.assertEquals(headers["Content-Type"], "text/xml")

    def test_extra_values_ignored(self):
        lambda_output = '{"statusCode": 200, "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", ' \
                        '"isBase64Encoded": false, "another_key": "some value"}'

        (status_code, headers, body) = LocalApigwService._parse_lambda_output(lambda_output,
                                                                              binary_types=[],
                                                                              flask_request=Mock())

        self.assertEquals(status_code, 200)
        self.assertEquals(headers, {"Content-Type": "application/json"})
        self.assertEquals(body, '{"message":"Hello from Lambda"}')

    def test_parse_returns_correct_tuple(self):
        lambda_output = '{"statusCode": 200, "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", ' \
                        '"isBase64Encoded": false}'

        (status_code, headers, body) = LocalApigwService._parse_lambda_output(lambda_output,
                                                                              binary_types=[],
                                                                              flask_request=Mock())

        self.assertEquals(status_code, 200)
        self.assertEquals(headers, {"Content-Type": "application/json"})
        self.assertEquals(body, '{"message":"Hello from Lambda"}')

    @patch('samcli.local.apigw.local_apigw_service.LocalApigwService._should_base64_decode_body')
    def test_parse_returns_decodes_base64_to_binary(self, should_decode_body_patch):
        should_decode_body_patch.return_value = True

        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode('utf-8')
        lambda_output = {"statusCode": 200,
                         "headers": {"Content-Type": "application/octet-stream"},
                         "body": base64_body,
                         "isBase64Encoded": False}

        (status_code, headers, body) = LocalApigwService._parse_lambda_output(json.dumps(lambda_output),
                                                                              binary_types=['*/*'],
                                                                              flask_request=Mock())

        self.assertEquals(status_code, 200)
        self.assertEquals(headers, {"Content-Type": "application/octet-stream"})
        self.assertEquals(body, binary_body)

    def test_status_code_not_int(self):
        lambda_output = '{"statusCode": "str", "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", ' \
                        '"isBase64Encoded": false}'

        with self.assertRaises(TypeError):
            LocalApigwService._parse_lambda_output(lambda_output,
                                                   binary_types=[],
                                                   flask_request=Mock())

    def test_status_code_negative_int(self):
        lambda_output = '{"statusCode": -1, "headers": {}, "body": "{\\"message\\":\\"Hello from Lambda\\"}", ' \
                            '"isBase64Encoded": false}'

        with self.assertRaises(TypeError):
            LocalApigwService._parse_lambda_output(lambda_output,
                                                   binary_types=[],
                                                   flask_request=Mock())

    def test_lambda_output_list_not_dict(self):
        lambda_output = '[]'

        with self.assertRaises(TypeError):
            LocalApigwService._parse_lambda_output(lambda_output,
                                                   binary_types=[],
                                                   flask_request=Mock())

    def test_lambda_output_not_json_serializable(self):
        lambda_output = 'some str'

        with self.assertRaises(ValueError):
            LocalApigwService._parse_lambda_output(lambda_output, binary_types=[], flask_request=Mock())

    def test_properties_are_null(self):
        lambda_output = '{"statusCode": 0, "headers": null, "body": null, ' \
                        '"isBase64Encoded": null}'

        (status_code, headers, body) = LocalApigwService._parse_lambda_output(lambda_output,
                                                                              binary_types=[],
                                                                              flask_request=Mock())

        self.assertEquals(status_code, 200)
        self.assertEquals(headers, {"Content-Type": "application/json"})
        self.assertEquals(body, "no data")


class TestService_construct_event(TestCase):

    def setUp(self):
        self.request_mock = Mock()
        self.request_mock.endpoint = "endpoint"
        self.request_mock.path = "path"
        self.request_mock.method = "GET"
        self.request_mock.remote_addr = "190.0.0.0"
        self.request_mock.get_data.return_value = b"DATA!!!!"
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"query": ["params"]}.items()
        self.request_mock.args = query_param_args_mock
        self.request_mock.headers = {"Content-Type": "application/json", "X-Test": "Value"}
        self.request_mock.view_args = {"path": "params"}
        self.request_mock.scheme = "http"

        expected = '{"body": "DATA!!!!", "httpMethod": "GET", ' \
                   '"queryStringParameters": {"query": "params"}, "resource": ' \
                   '"endpoint", "requestContext": {"httpMethod": "GET", "requestId": ' \
                   '"c6af9ac6-7b61-11e6-9a41-93e8deadbeef", "path": "endpoint", "extendedRequestId": null, ' \
                   '"resourceId": "123456", "apiId": "1234567890", "stage": "prod", "resourcePath": "endpoint", ' \
                   '"identity": {"accountId": null, "apiKey": null, "userArn": null, ' \
                   '"cognitoAuthenticationProvider": null, "cognitoIdentityPoolId": null, "userAgent": ' \
                   '"Custom User Agent String", "caller": null, "cognitoAuthenticationType": null, "sourceIp": ' \
                   '"190.0.0.0", "user": null}, "accountId": "123456789012"}, "headers": {"Content-Type": ' \
                   '"application/json", "X-Test": "Value", "X-Forwarded-Port": "3000", "X-Forwarded-Proto": "http"}, ' \
                   '"stageVariables": null, "path": "path", "pathParameters": {"path": "params"}, ' \
                   '"isBase64Encoded": false}'

        self.expected_dict = json.loads(expected)

    def test_construct_event_with_data(self):
        actual_event_str = LocalApigwService._construct_event(self.request_mock, 3000, binary_types=[])
        self.assertEquals(json.loads(actual_event_str), self.expected_dict)

    def test_construct_event_no_data(self):
        self.request_mock.get_data.return_value = None
        self.expected_dict["body"] = None

        actual_event_str = LocalApigwService._construct_event(self.request_mock, 3000, binary_types=[])
        self.assertEquals(json.loads(actual_event_str), self.expected_dict)

    @patch('samcli.local.apigw.local_apigw_service.LocalApigwService._should_base64_encode')
    def test_construct_event_with_binary_data(self, should_base64_encode_patch):
        should_base64_encode_patch.return_value = True

        binary_body = b"011000100110100101101110011000010111001001111001"  # binary in binary
        base64_body = base64.b64encode(binary_body).decode('utf-8')

        self.request_mock.get_data.return_value = binary_body
        self.expected_dict["body"] = base64_body
        self.expected_dict["isBase64Encoded"] = True

        actual_event_str = LocalApigwService._construct_event(self.request_mock, 3000, binary_types=[])
        self.assertEquals(json.loads(actual_event_str), self.expected_dict)

    def test_query_string_params_with_empty_params(self):
        request_mock = Mock()
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {}.items()
        request_mock.args = query_param_args_mock

        actual_query_string = LocalApigwService._query_string_params(request_mock)
        self.assertEquals(actual_query_string, {})

    def test_query_string_params_with_param_value_being_empty_list(self):
        request_mock = Mock()
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"param": []}.items()
        request_mock.args = query_param_args_mock

        actual_query_string = LocalApigwService._query_string_params(request_mock)
        self.assertEquals(actual_query_string, {"param": ""})

    def test_query_string_params_with_param_value_being_non_empty_list(self):
        request_mock = Mock()
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"param": ["a", "b"]}.items()
        request_mock.args = query_param_args_mock

        actual_query_string = LocalApigwService._query_string_params(request_mock)
        self.assertEquals(actual_query_string, {"param": "b"})


class TestService_should_base64_encode(TestCase):

    @parameterized.expand([
        param("Mimeyype is in binary types", ['image/gif'], 'image/gif'),
        param("Mimetype defined and binary types has */*", ['*/*'], 'image/gif'),
        param("*/* is in binary types with no mimetype defined", ['*/*'], None)
    ])
    def test_should_base64_encode_returns_true(self, test_case_name, binary_types, mimetype):
        self.assertTrue(LocalApigwService._should_base64_encode(binary_types, mimetype))

    @parameterized.expand([
        param("Mimetype is not in binary types", ['image/gif'], "application/octet-stream")
    ])
    def test_should_base64_encode_returns_false(self, test_case_name, binary_types, mimetype):
        self.assertFalse(LocalApigwService._should_base64_encode(binary_types, mimetype))
