"""API Gateway Local Service"""
import base64
import io
import json
import logging
from datetime import datetime
from time import time
from typing import List, Optional

from flask import Flask, request
from werkzeug.datastructures import Headers
from werkzeug.routing import BaseConverter
from werkzeug.serving import WSGIRequestHandler

from samcli.commands.local.lib.exceptions import UnsupportedInlineCodeError
from samcli.lib.providers.provider import Cors
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.events.api_event import (
    ApiGatewayLambdaEvent,
    ApiGatewayV2LambdaEvent,
    ContextHTTP,
    ContextIdentity,
    RequestContext,
    RequestContextV2,
)
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.local.services.base_local_service import BaseLocalService, LambdaOutputParser

from .path_converter import PathConverter
from .service_error_responses import ServiceErrorResponses

LOG = logging.getLogger(__name__)


class LambdaResponseParseException(Exception):
    """
    An exception raised when we fail to parse the response for Lambda
    """


class PayloadFormatVersionValidateException(Exception):
    """
    An exception raised when validation of payload format version fails
    """


class Route:
    API = "Api"
    HTTP = "HttpApi"
    ANY_HTTP_METHODS = ["GET", "DELETE", "PUT", "POST", "HEAD", "OPTIONS", "PATCH"]

    def __init__(
        self,
        function_name: Optional[str],
        path: str,
        methods: List[str],
        event_type: str = API,
        payload_format_version: Optional[str] = None,
        is_default_route: bool = False,
        operation_name=None,
        stack_path: str = "",
    ):
        """
        Creates an ApiGatewayRoute

        :param list(str) methods: http method
        :param function_name: Name of the Lambda function this API is connected to
        :param str path: Path off the base url
        :param str event_type: Type of the event. "Api" or "HttpApi"
        :param str payload_format_version: version of payload format
        :param bool is_default_route: determines if the default route or not
        :param string operation_name: Swagger operationId for the route
        :param str stack_path: path of the stack the route is located
        """
        self.methods = self.normalize_method(methods)
        self.function_name = function_name
        self.path = path
        self.event_type = event_type
        self.payload_format_version = payload_format_version
        self.is_default_route = is_default_route
        self.operation_name = operation_name
        self.stack_path = stack_path

    def __eq__(self, other):
        return (
            isinstance(other, Route)
            and sorted(self.methods) == sorted(other.methods)
            and self.function_name == other.function_name
            and self.path == other.path
            and self.operation_name == other.operation_name
            and self.stack_path == other.stack_path
        )

    def __hash__(self):
        route_hash = hash(f"{self.stack_path}-{self.function_name}-{self.path}")
        for method in sorted(self.methods):
            route_hash *= hash(method)
        return route_hash

    def normalize_method(self, methods):
        """
        Normalizes Http Methods. Api Gateway allows a Http Methods of ANY. This is a special verb to denote all
        supported Http Methods on Api Gateway.

        :param list methods: Http methods
        :return list: Either the input http_method or one of the _ANY_HTTP_METHODS (normalized Http Methods)
        """
        methods = [method.upper() for method in methods]
        if "ANY" in methods:
            return self.ANY_HTTP_METHODS
        return methods


class CatchAllPathConverter(BaseConverter):
    regex = ".+"
    weight = 300
    part_isolating = False

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


class LocalApigwService(BaseLocalService):
    _DEFAULT_PORT = 3000
    _DEFAULT_HOST = "127.0.0.1"

    def __init__(self, api, lambda_runner, static_dir=None, port=None, host=None, stderr=None):
        """
        Creates an ApiGatewayService

        Parameters
        ----------
        api : Api
           an Api object that contains the list of routes and properties
        lambda_runner : samcli.commands.local.lib.local_lambda.LocalLambdaRunner
            The Lambda runner class capable of invoking the function
        static_dir : str
            Directory from which to serve static files
        port : int
            Optional. port for the service to start listening on
            Defaults to 3000
        host : str
            Optional. host to start the service on
            Defaults to '127.0.0.1
        stderr : samcli.lib.utils.stream_writer.StreamWriter
            Optional stream writer where the stderr from Docker container should be written to
        """
        super().__init__(lambda_runner.is_debugging(), port=port, host=host)
        self.api = api
        self.lambda_runner = lambda_runner
        self.static_dir = static_dir
        self._dict_of_routes = {}
        self.stderr = stderr

    def create(self):
        """
        Creates a Flask Application that can be started.
        """
        # Setting sam local start-api to respond using HTTP/1.1 instead of the default HTTP/1.0
        WSGIRequestHandler.protocol_version = "HTTP/1.1"

        self._app = Flask(
            __name__,
            static_url_path="",  # Mount static files at root '/'
            static_folder=self.static_dir,  # Serve static files from this directory
        )

        # add converter to support catch-all route
        self._app.url_map.converters["path"] = CatchAllPathConverter

        # Prevent the dev server from emitting headers that will make the browser cache response by default
        self._app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

        # This will normalize all endpoints and strip any trailing '/'
        self._app.url_map.strict_slashes = False
        default_route = None

        for api_gateway_route in self.api.routes:
            if api_gateway_route.path == "$default":
                default_route = api_gateway_route
                continue
            path = PathConverter.convert_path_to_flask(api_gateway_route.path)
            for route_key in self._generate_route_keys(api_gateway_route.methods, path):
                self._dict_of_routes[route_key] = api_gateway_route
            self._app.add_url_rule(
                path,
                endpoint=path,
                view_func=self._request_handler,
                methods=api_gateway_route.methods,
                provide_automatic_options=False,
            )

        if default_route:
            LOG.debug("add catch-all route")
            all_methods = Route.ANY_HTTP_METHODS
            try:
                rules_iter = self._app.url_map.iter_rules("/")
                while True:
                    rule = next(rules_iter)
                    all_methods = [method for method in all_methods if method not in rule.methods]
            except (KeyError, StopIteration):
                pass

            self._add_catch_all_path(all_methods, "/", default_route)
            self._add_catch_all_path(Route.ANY_HTTP_METHODS, "/<path:any_path>", default_route)

        self._construct_error_handling()

    def _add_catch_all_path(self, methods, path, route):
        """
        Add the catch all route to the _app and the dictionary of routes.

        :param list(str) methods: List of HTTP Methods
        :param str path: Path off the base url
        :param Route route: contains the default route configurations
        """

        self._app.add_url_rule(
            path,
            endpoint=path,
            view_func=self._request_handler,
            methods=methods,
            provide_automatic_options=False,
        )
        for route_key in self._generate_route_keys(methods, path):
            self._dict_of_routes[route_key] = Route(
                function_name=route.function_name,
                path=path,
                methods=methods,
                event_type=Route.HTTP,
                payload_format_version=route.payload_format_version,
                is_default_route=True,
                stack_path=route.stack_path,
            )

    def _generate_route_keys(self, methods, path):
        """
        Generates the key to the _dict_of_routes based on the list of methods
        and path supplied

        Parameters
        ----------
        methods : List[str]
            List of HTTP Methods
        path : str
            Path off the base url

        Yields
        ------
        route_key : str
            the route key in the form of "Path:Method"
        """
        for method in methods:
            yield self._route_key(method, path)

    @staticmethod
    def _v2_route_key(method, path, is_default_route):
        if is_default_route:
            return "$default"
        return "{} {}".format(method, path)

    @staticmethod
    def _route_key(method, path):
        return "{}:{}".format(path, method)

    def _construct_error_handling(self):
        """
        Updates the Flask app with Error Handlers for different Error Codes
        """
        # Both path and method not present
        self._app.register_error_handler(404, ServiceErrorResponses.route_not_found)
        # Path is present, but method not allowed
        self._app.register_error_handler(405, ServiceErrorResponses.route_not_found)
        # Something went wrong
        self._app.register_error_handler(500, ServiceErrorResponses.lambda_failure_response)

    def _request_handler(self, **kwargs):
        """
        We handle all requests to the host:port. The general flow of handling a request is as follows

        * Fetch request from the Flask Global state. This is where Flask places the request and is per thread so
          multiple requests are still handled correctly
        * Find the Lambda function to invoke by doing a look up based on the request.endpoint and method
        * If we don't find the function, we will throw a 502 (just like the 404 and 405 responses we get
          from Flask.
        * Since we found a Lambda function to invoke, we construct the Lambda Event from the request
        * Then Invoke the Lambda function (docker container)
        * We then transform the response or errors we get from the Invoke and return the data back to
          the caller

        Parameters
        ----------
        kwargs dict
            Keyword Args that are passed to the function from Flask. This happens when we have path parameters

        Returns
        -------
        Response object
        """

        route = self._get_current_route(request)
        cors_headers = Cors.cors_to_headers(self.api.cors)

        # payloadFormatVersion can only support 2 values: "1.0" and "2.0"
        # so we want to do strict validation to make sure it has proper value if provided
        # https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html
        if route.payload_format_version not in [None, "1.0", "2.0"]:
            raise PayloadFormatVersionValidateException(
                f'{route.payload_format_version} is not a valid value. PayloadFormatVersion must be "1.0" or "2.0"'
            )

        method, endpoint = self.get_request_methods_endpoints(request)
        if method == "OPTIONS" and self.api.cors:
            headers = Headers(cors_headers)
            return self.service_response("", headers, 200)

        try:
            # TODO: Rewrite the logic below to use version 2.0 when an invalid value is provided
            # the Lambda Event 2.0 is only used for the HTTP API gateway with defined payload format version equal 2.0
            # or none, as the default value to be used is 2.0
            # https://docs.aws.amazon.com/apigatewayv2/latest/api-reference/apis-apiid-integrations.html#apis-apiid-integrations-prop-createintegrationinput-payloadformatversion
            if route.event_type == Route.HTTP and route.payload_format_version in [None, "2.0"]:
                apigw_endpoint = PathConverter.convert_path_to_api_gateway(endpoint)
                route_key = self._v2_route_key(method, apigw_endpoint, route.is_default_route)
                event = self._construct_v_2_0_event_http(
                    request,
                    self.port,
                    self.api.binary_media_types,
                    self.api.stage_name,
                    self.api.stage_variables,
                    route_key,
                )
            elif route.event_type == Route.API:
                # The OperationName is only sent to the Lambda Function from API Gateway V1(Rest API).
                event = self._construct_v_1_0_event(
                    request,
                    self.port,
                    self.api.binary_media_types,
                    self.api.stage_name,
                    self.api.stage_variables,
                    route.operation_name,
                )
            else:
                # For Http Apis with payload version 1.0, API Gateway never sends the OperationName.
                event = self._construct_v_1_0_event(
                    request,
                    self.port,
                    self.api.binary_media_types,
                    self.api.stage_name,
                    self.api.stage_variables,
                    None,
                )
        except UnicodeDecodeError as error:
            LOG.error("UnicodeDecodeError while processing HTTP request: %s", error)
            return ServiceErrorResponses.lambda_failure_response()

        stdout_stream = io.BytesIO()
        stdout_stream_writer = StreamWriter(stdout_stream, auto_flush=True)

        try:
            self.lambda_runner.invoke(route.function_name, event, stdout=stdout_stream_writer, stderr=self.stderr)
        except FunctionNotFound:
            return ServiceErrorResponses.lambda_not_found_response()
        except UnsupportedInlineCodeError:
            return ServiceErrorResponses.not_implemented_locally(
                "Inline code is not supported for sam local commands. Please write your code in a separate file."
            )

        lambda_response, _ = LambdaOutputParser.get_lambda_output(stdout_stream)

        try:
            if route.event_type == Route.HTTP and (
                not route.payload_format_version or route.payload_format_version == "2.0"
            ):
                (status_code, headers, body) = self._parse_v2_payload_format_lambda_output(
                    lambda_response, self.api.binary_media_types, request
                )
            else:
                (status_code, headers, body) = self._parse_v1_payload_format_lambda_output(
                    lambda_response, self.api.binary_media_types, request, route.event_type
                )
        except LambdaResponseParseException as ex:
            LOG.error("Invalid lambda response received: %s", ex)
            return ServiceErrorResponses.lambda_failure_response()

        return self.service_response(body, headers, status_code)

    def _get_current_route(self, flask_request):
        """
        Get the route (Route) based on the current request

        :param request flask_request: Flask Request
        :return: Route matching the endpoint and method of the request
        """
        method, endpoint = self.get_request_methods_endpoints(flask_request)

        route_key = self._route_key(method, endpoint)
        route = self._dict_of_routes.get(route_key, None)

        if not route:
            LOG.debug(
                "Lambda function for the route not found. This should not happen because Flask is "
                "already configured to serve all path/methods given to the service. "
                "Path=%s Method=%s RouteKey=%s",
                endpoint,
                method,
                route_key,
            )
            raise KeyError("Lambda function for the route not found")

        return route

    @staticmethod
    def get_request_methods_endpoints(flask_request):
        """
        Separated out for testing requests in request handler
        :param request flask_request: Flask Request
        :return: the request's endpoint and method
        """
        endpoint = flask_request.endpoint
        method = flask_request.method
        return method, endpoint

    # Consider moving this out to its own class. Logic is started to get dense and looks messy @jfuss
    @staticmethod
    def _parse_v1_payload_format_lambda_output(lambda_output: str, binary_types, flask_request, event_type):
        """
        Parses the output from the Lambda Container

        :param str lambda_output: Output from Lambda Invoke
        :param binary_types: list of binary types
        :param flask_request: flash request object
        :param event_type: determines the route event type
        :return: Tuple(int, dict, str, bool)
        """
        # pylint: disable-msg=too-many-statements
        try:
            json_output = json.loads(lambda_output)
        except ValueError as ex:
            raise LambdaResponseParseException("Lambda response must be valid json") from ex

        if not isinstance(json_output, dict):
            raise LambdaResponseParseException(f"Lambda returned {type(json_output)} instead of dict")

        if event_type == Route.HTTP and json_output.get("statusCode") is None:
            raise LambdaResponseParseException(f"Invalid API Gateway Response Key: statusCode is not in {json_output}")

        status_code = json_output.get("statusCode") or 200
        headers = LocalApigwService._merge_response_headers(
            json_output.get("headers") or {}, json_output.get("multiValueHeaders") or {}
        )

        body = json_output.get("body")
        if body is None:
            LOG.warning("Lambda returned empty body!")

        is_base_64_encoded = LocalApigwService.get_base_64_encoded(event_type, json_output)

        try:
            status_code = int(status_code)
            if status_code <= 0:
                raise ValueError
        except ValueError as ex:
            raise LambdaResponseParseException("statusCode must be a positive int") from ex

        try:
            if body:
                body = str(body)
        except ValueError as ex:
            raise LambdaResponseParseException(
                f"Non null response bodies should be able to convert to string: {body}"
            ) from ex

        invalid_keys = LocalApigwService._invalid_apig_response_keys(json_output, event_type)
        # HTTP API Gateway just skip the non allowed lambda response fields, but Rest API gateway fail on
        # the non allowed fields
        if event_type == Route.API and invalid_keys:
            raise LambdaResponseParseException(f"Invalid API Gateway Response Keys: {invalid_keys} in {json_output}")

        # If the customer doesn't define Content-Type default to application/json
        if "Content-Type" not in headers:
            LOG.info("No Content-Type given. Defaulting to 'application/json'.")
            headers["Content-Type"] = "application/json"

        try:
            # HTTP API Gateway always decode the lambda response only if isBase64Encoded field in response is True
            # regardless the response content-type
            # Rest API Gateway depends on the response content-type and the API configured BinaryMediaTypes to decide
            # if it will decode the response or not
            if (event_type == Route.HTTP and is_base_64_encoded) or (
                event_type == Route.API
                and LocalApigwService._should_base64_decode_body(
                    binary_types, flask_request, headers, is_base_64_encoded
                )
            ):
                body = base64.b64decode(body)
        except ValueError as ex:
            LambdaResponseParseException(str(ex))

        return status_code, headers, body

    @staticmethod
    def get_base_64_encoded(event_type, json_output):
        # The following behaviour is undocumented behaviour, and based on some trials
        # Http API gateway checks lambda response for isBase64Encoded field, and ignore base64Encoded
        # Rest API gateway checks first the field base64Encoded field, if not exist, it checks isBase64Encoded field

        if event_type == Route.API and json_output.get("base64Encoded") is not None:
            is_base_64_encoded = json_output.get("base64Encoded")
            field_name = "base64Encoded"
        elif json_output.get("isBase64Encoded") is not None:
            is_base_64_encoded = json_output.get("isBase64Encoded")
            field_name = "isBase64Encoded"
        else:
            is_base_64_encoded = False
            field_name = "isBase64Encoded"

        if isinstance(is_base_64_encoded, str) and is_base_64_encoded in ["true", "True", "false", "False"]:
            is_base_64_encoded = is_base_64_encoded in ["true", "True"]
        elif not isinstance(is_base_64_encoded, bool):
            raise LambdaResponseParseException(
                f"Invalid API Gateway Response Key: {is_base_64_encoded} is not a valid" f"{field_name}"
            )

        return is_base_64_encoded

    @staticmethod
    def _parse_v2_payload_format_lambda_output(lambda_output: str, binary_types, flask_request):
        """
        Parses the output from the Lambda Container. V2 Payload Format means that the event_type is only HTTP

        :param str lambda_output: Output from Lambda Invoke
        :param binary_types: list of binary types
        :param flask_request: flash request object
        :return: Tuple(int, dict, str, bool)
        """
        # pylint: disable-msg=too-many-statements
        # pylint: disable=too-many-branches
        try:
            json_output = json.loads(lambda_output)
        except ValueError as ex:
            raise LambdaResponseParseException("Lambda response must be valid json") from ex

        # lambda can return any valid json response in payload format version 2.0.
        # response can be a simple type like string, or integer
        # https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html#http-api-develop-integrations-lambda.response
        if isinstance(json_output, dict):
            body = json_output.get("body") if "statusCode" in json_output else json.dumps(json_output)
        else:
            body = json_output
            json_output = {}

        if body is None:
            LOG.warning("Lambda returned empty body!")

        status_code = json_output.get("statusCode") or 200
        headers = Headers(json_output.get("headers") or {})

        # cookies is a new field in payload format version 2.0 (a list)
        # https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html
        # we need to move cookies to Set-Cookie headers.
        # each cookie becomes a set-cookie header
        # MDN link: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie
        cookies = json_output.get("cookies")

        # cookies needs to be a list, otherwise the format is wrong and we can skip it
        if isinstance(cookies, list):
            for cookie in cookies:
                headers.add("Set-Cookie", cookie)

        is_base_64_encoded = json_output.get("isBase64Encoded") or False

        try:
            status_code = int(status_code)
            if status_code <= 0:
                raise ValueError
        except ValueError as ex:
            raise LambdaResponseParseException("statusCode must be a positive int") from ex

        try:
            if body:
                body = str(body)
        except ValueError as ex:
            raise LambdaResponseParseException(
                f"Non null response bodies should be able to convert to string: {body}"
            ) from ex

        # If the customer doesn't define Content-Type default to application/json
        if "Content-Type" not in headers:
            LOG.info("No Content-Type given. Defaulting to 'application/json'.")
            headers["Content-Type"] = "application/json"

        try:
            # HTTP API Gateway always decode the lambda response only if isBase64Encoded field in response is True
            # regardless the response content-type
            if is_base_64_encoded:
                # Note(xinhol): here in this method we change the type of the variable body multiple times
                # and confused mypy, we might want to avoid this and use multiple variables here.
                body = base64.b64decode(body)  # type: ignore
        except ValueError as ex:
            LambdaResponseParseException(str(ex))

        return status_code, headers, body

    @staticmethod
    def _invalid_apig_response_keys(output, event_type):
        allowable = {"statusCode", "body", "headers", "multiValueHeaders", "isBase64Encoded", "cookies"}
        if event_type == Route.API:
            allowable.add("base64Encoded")
        invalid_keys = output.keys() - allowable
        return invalid_keys

    @staticmethod
    def _should_base64_decode_body(binary_types, flask_request, lamba_response_headers, is_base_64_encoded):
        """
        Whether or not the body should be decoded from Base64 to Binary

        Parameters
        ----------
        binary_types list(basestring)
            Corresponds to self.binary_types (aka. what is parsed from SAM Template
        flask_request flask.request
            Flask request
        lamba_response_headers werkzeug.datastructures.Headers
            Headers Lambda returns
        is_base_64_encoded bool
            True if the body is Base64 encoded

        Returns
        -------
        True if the body from the request should be converted to binary, otherwise false

        """
        best_match_mimetype = flask_request.accept_mimetypes.best_match(lamba_response_headers.get_all("Content-Type"))
        is_best_match_in_binary_types = best_match_mimetype in binary_types or "*/*" in binary_types

        return best_match_mimetype and is_best_match_in_binary_types and is_base_64_encoded

    @staticmethod
    def _merge_response_headers(headers, multi_headers):
        """
        Merge multiValueHeaders headers with headers

        * If you specify values for both headers and multiValueHeaders, API Gateway merges them into a single list.
        * If the same key-value pair is specified in both, the value will only appear once.

        Parameters
        ----------
        headers dict
            Headers map from the lambda_response_headers
        multi_headers dict
            multiValueHeaders map from the lambda_response_headers

        Returns
        -------
        Merged list in accordance to the AWS documentation within a Flask Headers object

        """

        processed_headers = Headers(multi_headers)

        for header in headers:
            # Prevent duplication of values when the key-value pair exists in both
            # headers and multi_headers, but preserve order from multi_headers
            if header in multi_headers and headers[header] in multi_headers[header]:
                continue

            processed_headers.add(header, headers[header])

        return processed_headers

    @staticmethod
    def _construct_v_1_0_event(
        flask_request, port, binary_types, stage_name=None, stage_variables=None, operation_name=None
    ):
        """
        Helper method that constructs the Event to be passed to Lambda

        :param request flask_request: Flask Request
        :param port: the port number
        :param binary_types: list of binary types
        :param stage_name: Optional, the stage name string
        :param stage_variables: Optional, API Gateway Stage Variables
        :return: String representing the event
        """
        # pylint: disable-msg=too-many-locals

        identity = ContextIdentity(source_ip=flask_request.remote_addr)

        endpoint = PathConverter.convert_path_to_api_gateway(flask_request.endpoint)
        method = flask_request.method
        protocol = flask_request.environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        host = flask_request.host

        request_data = flask_request.get_data()

        request_mimetype = flask_request.mimetype

        is_base_64 = LocalApigwService._should_base64_encode(binary_types, request_mimetype)

        if is_base_64:
            LOG.debug("Incoming Request seems to be binary. Base64 encoding the request data before sending to Lambda.")
            request_data = base64.b64encode(request_data)

        if request_data:
            # Flask does not parse/decode the request data. We should do it ourselves
            # Note(xinhol): here we change request_data's type from bytes to str and confused mypy
            # We might want to consider to use a new variable here.
            request_data = request_data.decode("utf-8")

        query_string_dict, multi_value_query_string_dict = LocalApigwService._query_string_params(flask_request)

        context = RequestContext(
            resource_path=endpoint,
            http_method=method,
            stage=stage_name,
            identity=identity,
            path=endpoint,
            protocol=protocol,
            domain_name=host,
            operation_name=operation_name,
        )

        headers_dict, multi_value_headers_dict = LocalApigwService._event_headers(flask_request, port)

        event = ApiGatewayLambdaEvent(
            http_method=method,
            body=request_data,
            resource=endpoint,
            request_context=context,
            query_string_params=query_string_dict,
            multi_value_query_string_params=multi_value_query_string_dict,
            headers=headers_dict,
            multi_value_headers=multi_value_headers_dict,
            path_parameters=flask_request.view_args,
            path=flask_request.path,
            is_base_64_encoded=is_base_64,
            stage_variables=stage_variables,
        )

        event_str = json.dumps(event.to_dict(), sort_keys=True)
        LOG.debug("Constructed String representation of Event to invoke Lambda. Event: %s", event_str)
        return event_str

    @staticmethod
    def _construct_v_2_0_event_http(
        flask_request,
        port,
        binary_types,
        stage_name=None,
        stage_variables=None,
        route_key=None,
        request_time_epoch=int(time()),
        request_time=datetime.utcnow().strftime("%d/%b/%Y:%H:%M:%S +0000"),
    ):
        """
        Helper method that constructs the Event 2.0 to be passed to Lambda

        https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html

        :param request flask_request: Flask Request
        :param port: the port number
        :param binary_types: list of binary types
        :param stage_name: Optional, the stage name string
        :param stage_variables: Optional, API Gateway Stage Variables
        :param route_key: Optional, the route key for the route
        :return: String representing the event
        """
        # pylint: disable-msg=too-many-locals
        method = flask_request.method

        request_data = flask_request.get_data()

        request_mimetype = flask_request.mimetype

        is_base_64 = LocalApigwService._should_base64_encode(binary_types, request_mimetype)

        if is_base_64:
            LOG.debug("Incoming Request seems to be binary. Base64 encoding the request data before sending to Lambda.")
            request_data = base64.b64encode(request_data)

        if request_data is not None:
            # Flask does not parse/decode the request data. We should do it ourselves
            request_data = request_data.decode("utf-8")

        query_string_dict = LocalApigwService._query_string_params_v_2_0(flask_request)

        cookies = LocalApigwService._event_http_cookies(flask_request)
        headers = LocalApigwService._event_http_headers(flask_request, port)
        context_http = ContextHTTP(method=method, path=flask_request.path, source_ip=flask_request.remote_addr)
        context = RequestContextV2(
            http=context_http,
            route_key=route_key,
            stage=stage_name,
            request_time_epoch=request_time_epoch,
            request_time=request_time,
        )

        event = ApiGatewayV2LambdaEvent(
            route_key=route_key,
            raw_path=flask_request.path,
            raw_query_string=flask_request.query_string.decode("utf-8"),
            cookies=cookies,
            headers=headers,
            query_string_params=query_string_dict,
            request_context=context,
            body=request_data,
            path_parameters=flask_request.view_args,
            is_base_64_encoded=is_base_64,
            stage_variables=stage_variables,
        )

        event_str = json.dumps(event.to_dict())
        LOG.debug("Constructed String representation of Event Version 2.0 to invoke Lambda. Event: %s", event_str)
        return event_str

    @staticmethod
    def _query_string_params(flask_request):
        """
        Constructs an APIGW equivalent query string dictionary

        Parameters
        ----------
        flask_request request
            Request from Flask

        Returns dict (str: str), dict (str: list of str)
        -------
            Empty dict if no query params where in the request otherwise returns a dictionary of key to value

        """
        query_string_dict = {}
        multi_value_query_string_dict = {}

        # Flask returns an ImmutableMultiDict so convert to a dictionary that becomes
        # a dict(str: list) then iterate over
        for query_string_key, query_string_list in flask_request.args.lists():
            query_string_value_length = len(query_string_list)

            # if the list is empty, default to empty string
            if not query_string_value_length:
                query_string_dict[query_string_key] = ""
                multi_value_query_string_dict[query_string_key] = [""]
            else:
                query_string_dict[query_string_key] = query_string_list[-1]
                multi_value_query_string_dict[query_string_key] = query_string_list

        return query_string_dict, multi_value_query_string_dict

    @staticmethod
    def _query_string_params_v_2_0(flask_request):
        """
        Constructs an APIGW equivalent query string dictionary using the 2.0 format
        https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html#2.0

        Parameters
        ----------
        flask_request request
            Request from Flask

        Returns dict (str: str)
        -------
            Empty dict if no query params where in the request otherwise returns a dictionary of key to value

        """
        query_string_dict = {}

        # Flask returns an ImmutableMultiDict so convert to a dictionary that becomes
        # a dict(str: list) then iterate over
        query_string_dict = {
            query_string_key: ",".join(query_string_list)
            for query_string_key, query_string_list in flask_request.args.lists()
        }

        return query_string_dict

    @staticmethod
    def _event_headers(flask_request, port):
        """
        Constructs an APIGW equivalent headers dictionary

        Parameters
        ----------
        flask_request request
            Request from Flask
        int port
            Forwarded Port
        cors_headers dict
            Dict of the Cors properties

        Returns dict (str: str), dict (str: list of str)
        -------
            Returns a dictionary of key to list of strings

        """
        headers_dict = {}
        multi_value_headers_dict = {}

        # Multi-value request headers is not really supported by Flask.
        # See https://github.com/pallets/flask/issues/850
        for header_key in flask_request.headers.keys():
            headers_dict[header_key] = flask_request.headers.get(header_key)
            multi_value_headers_dict[header_key] = flask_request.headers.getlist(header_key)

        headers_dict["X-Forwarded-Proto"] = flask_request.scheme
        multi_value_headers_dict["X-Forwarded-Proto"] = [flask_request.scheme]

        headers_dict["X-Forwarded-Port"] = str(port)
        multi_value_headers_dict["X-Forwarded-Port"] = [str(port)]
        return headers_dict, multi_value_headers_dict

    @staticmethod
    def _event_http_cookies(flask_request):
        """
        All cookie headers in the request are combined with commas.

        https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html

        Parameters
        ----------
        flask_request request
            Request from Flask

        Returns list
        -------
            Returns a list of cookies

        """
        cookies = []
        for cookie_key in flask_request.cookies.keys():
            cookies.append("{}={}".format(cookie_key, flask_request.cookies.get(cookie_key)))
        return cookies

    @staticmethod
    def _event_http_headers(flask_request, port):
        """
        Duplicate headers are combined with commas.

        https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html

        Parameters
        ----------
        flask_request request
            Request from Flask

        Returns list
        -------
            Returns a list of cookies

        """
        headers = {}
        # Multi-value request headers is not really supported by Flask.
        # See https://github.com/pallets/flask/issues/850
        for header_key in flask_request.headers.keys():
            headers[header_key] = flask_request.headers.get(header_key)

        headers["X-Forwarded-Proto"] = flask_request.scheme
        headers["X-Forwarded-Port"] = str(port)
        return headers

    @staticmethod
    def _should_base64_encode(binary_types, request_mimetype):
        """
        Whether or not to encode the data from the request to Base64

        Parameters
        ----------
        binary_types list(basestring)
            Corresponds to self.binary_types (aka. what is parsed from SAM Template
        request_mimetype str
            Mimetype for the request

        Returns
        -------
            True if the data should be encoded to Base64 otherwise False

        """
        return request_mimetype in binary_types or "*/*" in binary_types
