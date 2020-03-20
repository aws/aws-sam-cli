"""API Gateway Local Service"""
import io
import json
import logging
import base64

from flask import Flask, request
from werkzeug.datastructures import Headers

from samcli.lib.providers.provider import Cors
from samcli.local.services.base_local_service import BaseLocalService, LambdaOutputParser
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.local.events.api_event import ContextIdentity, RequestContext, ApiGatewayLambdaEvent
from .service_error_responses import ServiceErrorResponses
from .path_converter import PathConverter

LOG = logging.getLogger(__name__)


class LambdaResponseParseException(Exception):
    """
    An exception raised when we fail to parse the response for Lambda
    """


class Route:
    ANY_HTTP_METHODS = ["GET", "DELETE", "PUT", "POST", "HEAD", "OPTIONS", "PATCH"]

    def __init__(self, function_name, path, methods):
        """
        Creates an ApiGatewayRoute

        :param list(str) methods: http method
        :param function_name: Name of the Lambda function this API is connected to
        :param str path: Path off the base url
        """
        self.methods = self.normalize_method(methods)
        self.function_name = function_name
        self.path = path

    def __eq__(self, other):
        return (
            isinstance(other, Route)
            and sorted(self.methods) == sorted(other.methods)
            and self.function_name == other.function_name
            and self.path == other.path
        )

    def __hash__(self):
        route_hash = hash(self.function_name) * hash(self.path)
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


class LocalApigwService(BaseLocalService):
    _DEFAULT_PORT = 3000
    _DEFAULT_HOST = "127.0.0.1"

    def __init__(self, api, lambda_runner, static_dir=None, port=None, host=None, stderr=None):
        """
        Creates an ApiGatewayService

        Parameters
        ----------
        api: Api
           an Api object that contains the list of routes and properties
        lambda_runner samcli.commands.local.lib.local_lambda.LocalLambdaRunner
            The Lambda runner class capable of invoking the function
        static_dir str
            Directory from which to serve static files
        port int
            Optional. port for the service to start listening on
            Defaults to 3000
        host str
            Optional. host to start the service on
            Defaults to '127.0.0.1
        stderr samcli.lib.utils.stream_writer.StreamWriter
            Optional stream writer where the stderr from Docker container should be written to
        """
        super(LocalApigwService, self).__init__(lambda_runner.is_debugging(), port=port, host=host)
        self.api = api
        self.lambda_runner = lambda_runner
        self.static_dir = static_dir
        self._dict_of_routes = {}
        self.stderr = stderr

    def create(self):
        """
        Creates a Flask Application that can be started.
        """

        self._app = Flask(
            __name__,
            static_url_path="",  # Mount static files at root '/'
            static_folder=self.static_dir,  # Serve static files from this directory
        )

        # This will normalize all endpoints and strip any trailing '/'
        self._app.url_map.strict_slashes = False

        for api_gateway_route in self.api.routes:
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

        self._construct_error_handling()

    def _generate_route_keys(self, methods, path):
        """
        Generates the key to the _dict_of_routes based on the list of methods
        and path supplied

        :param list(str) methods: List of HTTP Methods
        :param str path: Path off the base url
        :return: str of Path:Method
        """
        for method in methods:
            yield self._route_key(method, path)

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

        method, _ = self.get_request_methods_endpoints(request)
        if method == "OPTIONS" and self.api.cors:
            headers = Headers(cors_headers)
            return self.service_response("", headers, 200)

        try:
            event = self._construct_event(
                request, self.port, self.api.binary_media_types, self.api.stage_name, self.api.stage_variables
            )
        except UnicodeDecodeError:
            return ServiceErrorResponses.lambda_failure_response()

        stdout_stream = io.BytesIO()
        stdout_stream_writer = StreamWriter(stdout_stream, self.is_debugging)

        try:
            self.lambda_runner.invoke(route.function_name, event, stdout=stdout_stream_writer, stderr=self.stderr)
        except FunctionNotFound:
            return ServiceErrorResponses.lambda_not_found_response()

        lambda_response, lambda_logs, _ = LambdaOutputParser.get_lambda_output(stdout_stream)

        if self.stderr and lambda_logs:
            # Write the logs to stderr if available.
            self.stderr.write(lambda_logs)

        try:
            (status_code, headers, body) = self._parse_lambda_output(
                lambda_response, self.api.binary_media_types, request
            )
        except LambdaResponseParseException:
            LOG.error(str(LambdaResponseParseException))
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

    def get_request_methods_endpoints(self, flask_request):
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
    def _parse_lambda_output(lambda_output, binary_types, flask_request):
        """
        Parses the output from the Lambda Container

        :param str lambda_output: Output from Lambda Invoke
        :return: Tuple(int, dict, str, bool)
        """
        # pylint: disable-msg=too-many-statements
        try:
            json_output = json.loads(lambda_output)
        except ValueError:
            raise LambdaResponseParseException(f"Lambda response must be valid json: {lambda_output}")

        if not isinstance(json_output, dict):
            raise LambdaResponseParseException(f"Lambda returned {type(json_output)} instead of dict")

        status_code = json_output.get("statusCode") or 200
        headers = LocalApigwService._merge_response_headers(
            json_output.get("headers") or {}, json_output.get("multiValueHeaders") or {}
        )
        body = json_output.get("body")
        if body is None:
            LOG.warning("Lambda returned empty body!")
        is_base_64_encoded = json_output.get("isBase64Encoded") or False

        try:
            status_code = int(status_code)
            if status_code <= 0:
                raise ValueError
        except ValueError:
            message = "statusCode must be a positive int"
            LOG.error(message)
            raise LambdaResponseParseException(message)

        try:
            if body:
                body = str(body)
        except ValueError:
            message = "Non null response bodies should be able to convert to string: {}".format(body)
            LOG.error(message)
            raise LambdaResponseParseException(message)

        # API Gateway only accepts statusCode, body, headers, and isBase64Encoded in
        # a response shape.
        invalid_keys = LocalApigwService._invalid_apig_response_keys(json_output)
        if bool(invalid_keys):
            msg = "Invalid API Gateway Response Keys: " + str(invalid_keys) + " in " + str(json_output)
            LOG.error(msg)
            raise LambdaResponseParseException(msg)

        # If the customer doesn't define Content-Type default to application/json
        if "Content-Type" not in headers:
            LOG.info("No Content-Type given. Defaulting to 'application/json'.")
            headers["Content-Type"] = "application/json"

        try:
            if LocalApigwService._should_base64_decode_body(binary_types, flask_request, headers, is_base_64_encoded):
                body = base64.b64decode(body)
        except ValueError as ex:
            LambdaResponseParseException(str(ex))

        return status_code, headers, body

    @staticmethod
    def _invalid_apig_response_keys(output):
        allowable = {"statusCode", "body", "headers", "multiValueHeaders", "isBase64Encoded"}
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
    def _construct_event(flask_request, port, binary_types, stage_name=None, stage_variables=None):
        """
        Helper method that constructs the Event to be passed to Lambda

        :param request flask_request: Flask Request
        :return: String representing the event
        """
        # pylint: disable-msg=too-many-locals

        identity = ContextIdentity(source_ip=flask_request.remote_addr)

        endpoint = PathConverter.convert_path_to_api_gateway(flask_request.endpoint)
        method = flask_request.method

        request_data = flask_request.get_data()

        request_mimetype = flask_request.mimetype

        is_base_64 = LocalApigwService._should_base64_encode(binary_types, request_mimetype)

        if is_base_64:
            LOG.debug("Incoming Request seems to be binary. Base64 encoding the request data before sending to Lambda.")
            request_data = base64.b64encode(request_data)

        if request_data:
            # Flask does not parse/decode the request data. We should do it ourselves
            request_data = request_data.decode("utf-8")

        context = RequestContext(
            resource_path=endpoint, http_method=method, stage=stage_name, identity=identity, path=endpoint
        )

        headers_dict, multi_value_headers_dict = LocalApigwService._event_headers(flask_request, port)

        query_string_dict, multi_value_query_string_dict = LocalApigwService._query_string_params(flask_request)

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

        event_str = json.dumps(event.to_dict())
        LOG.debug("Constructed String representation of Event to invoke Lambda. Event: %s", event_str)
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
