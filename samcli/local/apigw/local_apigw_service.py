"""API Gateway Local Service"""

import base64
import json
import logging
from datetime import datetime
from io import BytesIO
from time import time
from typing import Any, Dict, List, Optional

from flask import Flask, Request, request
from werkzeug.datastructures import Headers
from werkzeug.routing import BaseConverter
from werkzeug.serving import WSGIRequestHandler

from samcli.commands.local.lib.exceptions import UnsupportedInlineCodeError
from samcli.commands.local.lib.local_lambda import LocalLambdaRunner
from samcli.lib.providers.provider import Api, Cors
from samcli.lib.telemetry.event import EventName, EventTracker, UsedFeature
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.apigw.authorizers.lambda_authorizer import LambdaAuthorizer
from samcli.local.apigw.event_constructor import construct_v1_event, construct_v2_event_http
from samcli.local.apigw.exceptions import (
    AuthorizerUnauthorizedRequest,
    InvalidLambdaAuthorizerResponse,
    InvalidSecurityDefinition,
    LambdaResponseParseException,
    PayloadFormatVersionValidateException,
)
from samcli.local.apigw.path_converter import PathConverter
from samcli.local.apigw.route import Route
from samcli.local.apigw.service_error_responses import ServiceErrorResponses
from samcli.local.events.api_event import (
    ContextHTTP,
    ContextIdentity,
    RequestContext,
    RequestContextV2,
)
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.local.services.base_local_service import BaseLocalService, LambdaOutputParser

LOG = logging.getLogger(__name__)


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

    def __init__(
        self,
        api: Api,
        lambda_runner: LocalLambdaRunner,
        static_dir: Optional[str] = None,
        port: Optional[int] = None,
        host: Optional[str] = None,
        stderr: Optional[StreamWriter] = None,
    ):
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
        self._dict_of_routes: Dict[str, Route] = {}
        self.stderr = stderr

        self._click_session_id = None

        try:
            # save the session ID for telemetry event sending
            from samcli.cli.context import Context

            ctx = Context.get_current_context()

            if ctx:
                self._click_session_id = ctx.session_id
        except RuntimeError:
            LOG.debug("Not able to get click context in APIGW service")

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

    def _add_catch_all_path(self, methods: List[str], path: str, route: Route):
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
                authorizer_name=route.authorizer_name,
                authorizer_object=route.authorizer_object,
                use_default_authorizer=route.use_default_authorizer,
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

    def _create_method_arn(self, flask_request: Request, event_type: str) -> str:
        """
        Creates a method ARN with fake AWS values

        Parameters
        ----------
        flask_request: Request
            Flask request object to get method and path
        event_type: str
            Type of event (API or HTTP)

        Returns
        -------
        str
            A built method ARN with fake values
        """
        context = RequestContext() if event_type == Route.API else RequestContextV2()
        method, path = flask_request.method, flask_request.path

        return (
            f"arn:aws:execute-api:us-east-1:{context.account_id}:"  # type: ignore
            f"{context.api_id}/{self.api.stage_name}/{method}{path}"
        )

    def _generate_lambda_token_authorizer_event(
        self, flask_request: Request, route: Route, lambda_authorizer: LambdaAuthorizer
    ) -> dict:
        """
        Creates a Lambda authorizer token event

        Parameters
        ----------
        flask_request: Request
            Flask request object to get method and path
        route: Route
            Route object representing the endpoint to be invoked later
        lambda_authorizer: LambdaAuthorizer
            The Lambda authorizer the route is using

        Returns
        -------
        dict
            Basic dictionary containing a type and authorizationToken
        """
        method_arn = self._create_method_arn(flask_request, route.event_type)

        headers = {"headers": flask_request.headers}

        # V1 token based authorizers should always have a single identity source
        if len(lambda_authorizer.identity_sources) != 1:
            raise InvalidSecurityDefinition(
                "An invalid token based Lambda Authorizer was found, there should be one header identity source"
            )

        identity_source = lambda_authorizer.identity_sources[0]
        authorization_token = identity_source.find_identity_value(**headers)

        return {
            "type": LambdaAuthorizer.TOKEN.upper(),
            "authorizationToken": str(authorization_token),
            "methodArn": method_arn,
        }

    def _generate_lambda_request_authorizer_event_http(
        self, lambda_authorizer_payload: str, identity_values: list, method_arn: str
    ) -> dict:
        """
        Helper method to generate part of the event required for different payload versions
        for API Gateway V2

        Parameters
        ----------
        lambda_authorizer_payload: str
            The payload version of the Lambda authorizer
        identity_values: list
            A list of string identity values
        method_arn: str
            The method ARN for the endpoint

        Returns
        -------
        dict
            Dictionary containing partial Lambda authorizer event
        """
        if lambda_authorizer_payload == LambdaAuthorizer.PAYLOAD_V2:
            # payload 2.0 expects a list of strings
            return {"identitySource": identity_values, "routeArn": method_arn}
        else:
            # payload 1.0 expects a comma deliminated string that is the same
            # for both identitySource and authorizationToken
            all_identity_values_string = ",".join(identity_values)

            return {
                "identitySource": all_identity_values_string,
                "authorizationToken": all_identity_values_string,
                "methodArn": method_arn,
            }

    def _generate_lambda_request_authorizer_event(
        self, flask_request: Request, route: Route, lambda_authorizer: LambdaAuthorizer
    ) -> dict:
        """
        Creates a Lambda authorizer request event

        Parameters
        ----------
        flask_request: Request
            Flask request object to get method and path
        route: Route
            Route object representing the endpoint to be invoked later
        lambda_authorizer: LambdaAuthorizer
            The Lambda authorizer the route is using

        Returns
        -------
        dict
            A Lambda authorizer event
        """
        method_arn = self._create_method_arn(flask_request, route.event_type)
        method, endpoint = self.get_request_methods_endpoints(flask_request)

        # generate base lambda event and load it into a dict
        lambda_event = self._generate_lambda_event(flask_request, route, method, endpoint)
        lambda_event.update({"type": LambdaAuthorizer.REQUEST.upper()})

        # build context to form identity values
        context = (
            self._build_v1_context(route)
            if lambda_authorizer.payload_version == LambdaAuthorizer.PAYLOAD_V1
            else self._build_v2_context(route)
        )

        if route.event_type == Route.API:
            # v1 requests only add method ARN
            lambda_event.update({"methodArn": method_arn})
        else:
            # kwargs to pass into identity value finder
            kwargs = {
                "headers": flask_request.headers,
                "querystring": flask_request.query_string.decode("utf-8"),
                "context": context,
                "stageVariables": self.api.stage_variables,
            }

            # find and build all identity sources
            all_identity_values = []
            for identity_source in lambda_authorizer.identity_sources:
                value = identity_source.find_identity_value(**kwargs)

                if value:
                    # all identity values must be a string
                    all_identity_values.append(str(value))

            lambda_event.update(
                self._generate_lambda_request_authorizer_event_http(
                    lambda_authorizer.payload_version, all_identity_values, method_arn
                )
            )

        return lambda_event

    def _generate_lambda_authorizer_event(
        self, flask_request: Request, route: Route, lambda_authorizer: LambdaAuthorizer
    ) -> dict:
        """
        Generate a Lambda authorizer event

        Parameters
        ----------
        flask_request: Request
            Flask request object to get method and endpoint
        route: Route
            Route object representing the endpoint to be invoked later
        lambda_authorizer: LambdaAuthorizer
            The Lambda authorizer the route is using

        Returns
        -------
        str
            A JSON string containing event properties
        """
        authorizer_events = {
            LambdaAuthorizer.TOKEN: self._generate_lambda_token_authorizer_event,
            LambdaAuthorizer.REQUEST: self._generate_lambda_request_authorizer_event,
        }

        kwargs: Dict[str, Any] = {
            "flask_request": flask_request,
            "route": route,
            "lambda_authorizer": lambda_authorizer,
        }

        return authorizer_events[lambda_authorizer.type](**kwargs)

    def _generate_lambda_event(self, flask_request: Request, route: Route, method: str, endpoint: str) -> dict:
        """
        Helper function to generate the correct Lambda event

        Parameters
        ----------
        flask_request: Request
            The global Flask Request object
        route: Route
            The Route that was called
        method: str
            The method of the request (eg. GET, POST) from the Flask request
        endpoint: str
            The endpoint of the request from the Flask request

        Returns
        -------
        str
            JSON string of event properties
        """
        # TODO: Rewrite the logic below to use version 2.0 when an invalid value is provided
        # the Lambda Event 2.0 is only used for the HTTP API gateway with defined payload format version equal 2.0
        # or none, as the default value to be used is 2.0
        # https://docs.aws.amazon.com/apigatewayv2/latest/api-reference/apis-apiid-integrations.html#apis-apiid-integrations-prop-createintegrationinput-payloadformatversion
        if route.event_type == Route.HTTP and route.payload_format_version in [None, "2.0"]:
            apigw_endpoint = PathConverter.convert_path_to_api_gateway(endpoint)
            route_key = self._v2_route_key(method, apigw_endpoint, route.is_default_route)

            return construct_v2_event_http(
                flask_request=flask_request,
                port=self.port,
                binary_types=self.api.binary_media_types,
                stage_name=self.api.stage_name,
                stage_variables=self.api.stage_variables,
                route_key=route_key,
            )

        # For Http Apis with payload version 1.0, API Gateway never sends the OperationName.
        route_key = route.operation_name if route.event_type == Route.API else None

        return construct_v1_event(
            flask_request=flask_request,
            port=self.port,
            binary_types=self.api.binary_media_types,
            stage_name=self.api.stage_name,
            stage_variables=self.api.stage_variables,
            operation_name=route_key,
        )

    def _build_v1_context(self, route: Route) -> Dict[str, Any]:
        """
        Helper function to a 1.0 request context

        Parameters
        ----------
        route: Route
            The Route object that was invoked

        Returns
        -------
        dict
            JSON object containing context variables
        """
        identity = ContextIdentity(source_ip=request.remote_addr)

        protocol = request.environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        host = request.host

        operation_name = route.operation_name if route.event_type == Route.API else None

        endpoint = PathConverter.convert_path_to_api_gateway(request.endpoint)
        method = request.method

        context = RequestContext(
            resource_path=endpoint,
            http_method=method,
            stage=self.api.stage_name,
            identity=identity,
            path=endpoint,
            protocol=protocol,
            domain_name=host,
            operation_name=operation_name,
        )

        return context.to_dict()

    def _build_v2_context(self, route: Route) -> Dict[str, Any]:
        """
        Helper function to a 2.0 request context

        Parameters
        ----------
        route: Route
            The Route object that was invoked

        Returns
        -------
        dict
            JSON object containing context variables
        """
        endpoint = PathConverter.convert_path_to_api_gateway(request.endpoint)
        method = request.method

        apigw_endpoint = PathConverter.convert_path_to_api_gateway(endpoint)
        route_key = self._v2_route_key(method, apigw_endpoint, route.is_default_route)

        request_time_epoch = int(time())
        request_time = datetime.utcnow().strftime("%d/%b/%Y:%H:%M:%S +0000")

        context_http = ContextHTTP(method=method, path=request.path, source_ip=request.remote_addr)
        context = RequestContextV2(
            http=context_http,
            route_key=route_key,
            stage=self.api.stage_name,
            request_time_epoch=request_time_epoch,
            request_time=request_time,
        )

        return context.to_dict()

    def _valid_identity_sources(self, request: Request, route: Route) -> bool:
        """
        Validates if the route contains all the valid identity sources defined in the route's Lambda Authorizer

        Parameters
        ----------
        request: Request
            Flask request object containing incoming request variables
        route: Route
            the Route object that contains the Lambda Authorizer definition

        Returns
        -------
        bool
            true if all the identity sources are present and valid
        """
        lambda_auth = route.authorizer_object

        if not isinstance(lambda_auth, LambdaAuthorizer):
            return False

        identity_sources = lambda_auth.identity_sources

        context = (
            self._build_v1_context(route)
            if lambda_auth.payload_version == LambdaAuthorizer.PAYLOAD_V1
            else self._build_v2_context(route)
        )

        kwargs = {
            "headers": request.headers,
            "querystring": request.query_string.decode("utf-8"),
            "context": context,
            "stageVariables": self.api.stage_variables,
            "validation_expression": lambda_auth.validation_string,
        }

        for validator in identity_sources:
            if not validator.is_valid(**kwargs):
                return False

        return True

    def _invoke_lambda_function(self, lambda_function_name: str, event: dict) -> str:
        """
        Helper method to invoke a function and setup stdout+stderr

        Parameters
        ----------
        lambda_function_name: str
            The name of the Lambda function to invoke
        event: dict
            The event object to pass into the Lambda function

        Returns
        -------
        str
            A string containing the output from the Lambda function
        """
        with BytesIO() as stdout:
            event_str = json.dumps(event, sort_keys=True)
            stdout_writer = StreamWriter(stdout, auto_flush=True)

            self.lambda_runner.invoke(lambda_function_name, event_str, stdout=stdout_writer, stderr=self.stderr)
            lambda_response, _ = LambdaOutputParser.get_lambda_output(stdout)

        return lambda_response

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

        route: Route = self._get_current_route(request)
        cors_headers = Cors.cors_to_headers(self.api.cors)
        lambda_authorizer = route.authorizer_object

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

        # check for LambdaAuthorizer since that is the only authorizer we currently support
        if isinstance(lambda_authorizer, LambdaAuthorizer) and not self._valid_identity_sources(request, route):
            return ServiceErrorResponses.missing_lambda_auth_identity_sources()

        try:
            route_lambda_event = self._generate_lambda_event(request, route, method, endpoint)
            auth_lambda_event = None

            if lambda_authorizer:
                auth_lambda_event = self._generate_lambda_authorizer_event(request, route, lambda_authorizer)
        except UnicodeDecodeError as error:
            LOG.error("UnicodeDecodeError while processing HTTP request: %s", error)
            return ServiceErrorResponses.lambda_failure_response()

        try:
            lambda_authorizer_exception = None
            auth_service_error = None

            if lambda_authorizer:
                self._invoke_parse_lambda_authorizer(lambda_authorizer, auth_lambda_event, route_lambda_event, route)
        except AuthorizerUnauthorizedRequest as ex:
            auth_service_error = ServiceErrorResponses.lambda_authorizer_unauthorized()
            lambda_authorizer_exception = ex
        except InvalidLambdaAuthorizerResponse as ex:
            auth_service_error = ServiceErrorResponses.lambda_failure_response()
            lambda_authorizer_exception = ex
        except FunctionNotFound as ex:
            lambda_authorizer_exception = ex

            LOG.warning(
                "Failed to find a Function to invoke a Lambda authorizer, verify that "
                "this Function is defined and exists locally in the template."
            )
        except Exception as ex:
            # re-raise the catch all exception after we track it in our telemetry
            lambda_authorizer_exception = ex
            raise ex
        finally:
            exception_name = type(lambda_authorizer_exception).__name__ if lambda_authorizer_exception else None

            EventTracker.track_event(
                event_name=EventName.USED_FEATURE.value,
                event_value=UsedFeature.INVOKED_CUSTOM_LAMBDA_AUTHORIZERS.value,
                session_id=self._click_session_id,
                exception_name=exception_name,
            )

            if lambda_authorizer_exception:
                LOG.error("Lambda authorizer failed to invoke successfully: %s", exception_name)

            if auth_service_error:
                return auth_service_error

        endpoint_service_error = None
        try:
            # invoke the route's Lambda function
            lambda_response = self._invoke_lambda_function(route.function_name, route_lambda_event)
        except FunctionNotFound:
            endpoint_service_error = ServiceErrorResponses.lambda_not_found_response()
        except UnsupportedInlineCodeError:
            endpoint_service_error = ServiceErrorResponses.not_implemented_locally(
                "Inline code is not supported for sam local commands. Please write your code in a separate file."
            )

        if endpoint_service_error:
            return endpoint_service_error

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

    def _invoke_parse_lambda_authorizer(
        self, lambda_authorizer: LambdaAuthorizer, auth_lambda_event: dict, route_lambda_event: dict, route: Route
    ) -> None:
        """
        Helper method to invoke and parse the output of a Lambda authorizer

        Parameters
        ----------
        lambda_authorizer: LambdaAuthorizer
            The route's Lambda authorizer
        auth_lambda_event: dict
            The event to pass to the Lambda authorizer
        route_lambda_event: dict
            The event to pass into the route
        route: Route
            The route that is being called
        """
        lambda_auth_response = self._invoke_lambda_function(lambda_authorizer.lambda_name, auth_lambda_event)
        method_arn = self._create_method_arn(request, route.event_type)

        if not lambda_authorizer.is_valid_response(lambda_auth_response, method_arn):
            raise AuthorizerUnauthorizedRequest(f"Request is not authorized for {method_arn}")

        # update route context to include any context that may have been passed from authorizer
        original_context = route_lambda_event.get("requestContext", {})

        context = lambda_authorizer.get_context(lambda_auth_response)

        # payload V2 responses have the passed context under the "lambda" key
        if route.event_type == Route.HTTP and route.payload_format_version in [None, "2.0"]:
            original_context.update({"authorizer": {"lambda": context}})
        else:
            original_context.update({"authorizer": context})

        route_lambda_event.update({"requestContext": original_context})

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
