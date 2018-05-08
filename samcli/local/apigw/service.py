"""API Gateway Local Service"""
import io
import json
import logging
import base64

from flask import Flask, request, Response

from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.local.events.api_event import ContextIdentity, RequestContext, ApiGatewayLambdaEvent
from .service_error_responses import ServiceErrorResponses
from .path_converter import PathConverter

LOG = logging.getLogger(__name__)


class Route(object):

    def __init__(self, methods, function_name, path, binary_types=None):
        """
        Creates an ApiGatewayRoute

        :param list(str) methods: List of HTTP Methods
        :param function_name: Name of the Lambda function this API is connected to
        :param str path: Path off the base url
        """
        self.methods = methods
        self.function_name = function_name
        self.path = path
        self.binary_types = binary_types or []


class Service(object):

    _DEFAULT_PORT = 3000
    _DEFAULT_HOST = '127.0.0.1'

    def __init__(self, routing_list, lambda_runner, static_dir=None, port=None, host=None, stderr=None):
        """
        Creates an ApiGatewayService

        :param list(ApiGatewayCallModel) routing_list: A list of the Model that represent
          the service paths to create.
        :param samcli.commands.local.lib.local_lambda.LocalLambdaRunner lambda_runner: The Lambda runner class capable
            of invoking the function
        :param str static_dir: Directory from which to serve static files
        :param int port: Optional. port for the service to start listening on
          Defaults to 3000
        :param str host: Optional. host to start the service on
          Defaults to '0.0.0.0'
        :param io.BaseIO stderr: Optional stream where the stderr from Docker container should be written to
        """
        self.routing_list = routing_list
        self.lambda_runner = lambda_runner
        self.static_dir = static_dir
        self.port = port or self._DEFAULT_PORT
        self.host = host or self._DEFAULT_HOST
        self._dict_of_routes = {}
        self._app = None
        self.stderr = stderr

    def create(self):
        """
        Creates a Flask Application that can be started.
        """

        self._app = Flask(__name__,
                          static_url_path="",  # Mount static files at root '/'
                          static_folder=self.static_dir  # Serve static files from this directory
                          )

        for api_gateway_route in self.routing_list:
            path = PathConverter.convert_path_to_flask(api_gateway_route.path)
            for route_key in self._generate_route_keys(api_gateway_route.methods,
                                                       path):
                self._dict_of_routes[route_key] = api_gateway_route

            self._app.add_url_rule(path,
                                   endpoint=path,
                                   view_func=self._request_handler,
                                   methods=api_gateway_route.methods)

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
        return '{}:{}'.format(path, method)

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

    def run(self):
        """
        This starts up the (threaded) Local Server.
        Note: This is a **blocking call**

        :raise RuntimeError: If the service was not created
        """

        if not self._app:
            raise RuntimeError("The application must be created before running")

        # Flask can operate as a single threaded server (which is default) and a multi-threaded server which is
        # more for development. When the Lambda container is going to be debugged, then it does not make sense
        # to turn on multi-threading because customers can realistically attach only one container at a time to
        # the debugger. Keeping this single threaded also enables the Lambda Runner to handle Ctrl+C in order to
        # kill the container gracefully (Ctrl+C can be handled only by the main thread)
        multi_threaded = not self.lambda_runner.is_debugging()

        LOG.debug("Local API Server starting up. Multi-threading = %s", multi_threaded)
        self._app.run(threaded=multi_threaded, host=self.host, port=self.port)

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

        :param kwargs dict: Keyword Args that are passed to the function from Flask. This happens when we have
            Path Parameters.
        :return: Response object
        """
        route = self._get_current_route(request)

        try:
            event = self._construct_event(request, self.port, route.binary_types)
        except UnicodeDecodeError:
            return ServiceErrorResponses.lambda_failure_response()

        stdout_stream = io.BytesIO()

        try:
            self.lambda_runner.invoke(route.function_name, event, stdout=stdout_stream, stderr=self.stderr)
        except FunctionNotFound:
            return ServiceErrorResponses.lambda_not_found_response()

        lambda_response, lambda_logs = self._get_lambda_output(stdout_stream)

        if self.stderr and lambda_logs:
            # Write the logs to stderr if available.
            self.stderr.write(lambda_logs)

        try:
            (status_code, headers, body) = self._parse_lambda_output(lambda_response,
                                                                     route.binary_types,
                                                                     request)
        except (KeyError, TypeError, ValueError):
            LOG.error("Function returned an invalid response (must include one of: body, headers or "
                      "statusCode in the response object). Response received: %s", lambda_response)
            return ServiceErrorResponses.lambda_failure_response()

        return self._service_response(body, headers, status_code)

    @staticmethod
    def _service_response(body, headers, status_code):
        """
        Constructs a Flask Response from the body, headers, and status_code.

        :param str body: Response body as a string
        :param dict headers: headers for the response
        :param int status_code: status_code for response
        :return: Flask Response
        """
        response = Response(body)
        response.headers = headers
        response.status_code = status_code
        return response

    def _get_current_route(self, flask_request):
        """
        Get the route (Route) based on the current request

        :param request flask_request: Flask Request
        :return: Route matching the endpoint and method of the request
        """
        endpoint = flask_request.endpoint
        method = flask_request.method

        route_key = self._route_key(method, endpoint)
        route = self._dict_of_routes.get(route_key, None)

        if not route:
            LOG.debug("Lambda function for the route not found. This should not happen because Flask is "
                      "already configured to serve all path/methods given to the service. "
                      "Path=%s Method=%s RouteKey=%s", endpoint, method, route_key)
            raise KeyError("Lambda function for the route not found")

        return route

    @staticmethod
    def _get_lambda_output(stdout_stream):
        """
        This method will extract read the given stream and return the response from Lambda function separated out
        from any log statements it might have outputted. Logs end up in the stdout stream if the Lambda function
        wrote directly to stdout using System.out.println or equivalents.

        Parameters
        ----------
        stdout_stream : io.BaseIO
            Stream to fetch data from

        Returns
        -------
        str
            String data containing response from Lambda function
        str
            String data containng logs statements, if any.
        """
        # We only want the last line of stdout, because it's possible that
        # the function may have written directly to stdout using
        # System.out.println or similar, before docker-lambda output the result
        stdout_data = stdout_stream.getvalue().rstrip('\n')

        # Usually the output is just one line and contains response as JSON string, but if the Lambda function
        # wrote anything directly to stdout, there will be additional lines. So just extract the last line as
        # response and everything else as log output.
        lambda_response = stdout_data
        lambda_logs = None

        last_line_position = stdout_data.rfind('\n')
        if last_line_position > 0:
            # So there are multiple lines. Separate them out.
            # Everything but the last line are logs
            lambda_logs = stdout_data[:last_line_position]
            # Last line is Lambda response. Make sure to strip() so we get rid of extra whitespaces & newlines around
            lambda_response = stdout_data[last_line_position:].strip()

        return lambda_response, lambda_logs

    # Consider moving this out to its own class. Logic is started to get dense and looks messy @jfuss
    @staticmethod
    def _parse_lambda_output(lambda_output, binary_types, flask_request):
        """
        Parses the output from the Lambda Container

        :param str lambda_output: Output from Lambda Invoke
        :return: Tuple(int, dict, str, bool)
        """
        json_output = json.loads(lambda_output)

        if not isinstance(json_output, dict):
            raise TypeError("Lambda returned %{s} instead of dict", type(json_output))

        status_code = json_output.get("statusCode") or 200
        headers = json_output.get("headers") or {}
        body = json_output.get("body") or "no data"
        is_base_64_encoded = json_output.get("isBase64Encoded") or False

        if not isinstance(status_code, int) or status_code <= 0:
            message = "statusCode must be a positive int"
            LOG.error(message)
            raise TypeError(message)

        # If the customer doesn't define Content-Type default to application/json
        if "Content-Type" not in headers:
            LOG.info("No Content-Type given. Defaulting to 'application/json'.")
            headers["Content-Type"] = "application/json"

        if Service._should_base64_decode_body(binary_types, flask_request, headers, is_base_64_encoded):
            body = base64.b64decode(body)

        return status_code, headers, body

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
        lamba_response_headers dict
            Headers Lambda returns
        is_base_64_encoded bool
            True if the body is Base64 encoded

        Returns
        -------
        True if the body from the request should be converted to binary, otherwise false

        """
        best_match_mimetype = flask_request.accept_mimetypes.best_match([lamba_response_headers["Content-Type"]])
        is_best_match_in_binary_types = best_match_mimetype in binary_types or '*/*' in binary_types

        return best_match_mimetype and is_best_match_in_binary_types and is_base_64_encoded

    @staticmethod
    def _construct_event(flask_request, port, binary_types):
        """
        Helper method that constructs the Event to be passed to Lambda

        :param request flask_request: Flask Request
        :return: String representing the event
        """

        identity = ContextIdentity(source_ip=flask_request.remote_addr)

        endpoint = PathConverter.convert_path_to_api_gateway(flask_request.endpoint)
        method = flask_request.method

        request_data = flask_request.data

        request_mimetype = flask_request.mimetype

        is_base_64 = Service._should_base64_encode(binary_types, request_mimetype)

        if is_base_64:
            LOG.debug("Incoming Request seems to be binary. Base64 encoding the request data before sending to Lambda.")
            request_data = base64.b64encode(request_data)
        elif request_data:
            # Flask does not parse/decode the request data. We should do it ourselves
            request_data = request_data.decode('utf-8')

        context = RequestContext(resource_path=endpoint,
                                 http_method=method,
                                 stage="prod",
                                 identity=identity,
                                 path=endpoint)

        event_headers = dict(flask_request.headers)
        event_headers["X-Forwarded-Proto"] = flask_request.scheme
        event_headers["X-Forwarded-Port"] = str(port)

        event = ApiGatewayLambdaEvent(http_method=method,
                                      body=request_data,
                                      resource=endpoint,
                                      request_context=context,
                                      query_string_params=flask_request.args,
                                      headers=event_headers,
                                      path_parameters=flask_request.view_args,
                                      path=flask_request.path,
                                      is_base_64_encoded=is_base_64)

        event_str = json.dumps(event.to_dict())
        LOG.debug("Constructed String representation of Event to invoke Lambda. Event: %s", event_str)
        return event_str

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
