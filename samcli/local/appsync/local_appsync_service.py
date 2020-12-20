"""AppSync Local Service"""
import io
import json
import logging
import base64

from flask import Flask, request, jsonify
from werkzeug.datastructures import Headers
from werkzeug.routing import BaseConverter
from ariadne import load_schema_from_path, ObjectType, make_executable_schema, graphql_sync
from ariadne.constants import PLAYGROUND_HTML

from samcli.local.services.base_local_service import BaseLocalService, LambdaOutputParser
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.lambdafn.exceptions import FunctionNotFound

LOG = logging.getLogger(__name__)


class Resolver:
    def __init__(self, function_name, object_type, field_name):
        """
        Creates an AppSyncResolver

        :param function_name: Name of the Lambda function this resolver is connected to
        :param str object_type: Root object type in GraphQL schema, e.g. Query or Mutation
        :param str field_name: Field name for resolver in GraphQL schema
        """
        self.function_name = function_name
        self.field_name = field_name
        self.object_type = object_type

    def __eq__(self, other):
        return (
            isinstance(other, Resolver)
            and self.function_name == other.function_name
            and self.field_name == other.field_name
            and self.object_type == other.object_type
        )


class LocalAppSyncService(BaseLocalService):
    _DEFAULT_PORT = 3000
    _DEFAULT_HOST = "127.0.0.1"

    def __init__(self, api, lambda_runner, static_dir=None, port=None, host=None, stderr=None):
        """
        Creates an AppSyncService

        Parameters
        ----------
        api: GraphQLApi
           an Api object that contains the list of resolvers and schema path
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
        super().__init__(lambda_runner.is_debugging(), port=port, host=host)
        self.api = api
        self.lambda_runner = lambda_runner
        self.static_dir = static_dir
        self._dict_of_routes = {}
        self.stderr = stderr
        self.executable_schema = None

    def create(self):
        """
        Creates a Flask Application that can be started.
        """

        self._app = Flask(
            __name__,
            static_url_path="",  # Mount static files at root '/'
            static_folder=self.static_dir,  # Serve static files from this directory
        )

        # Prevent the dev server from emitting headers that will make the browser cache response by default
        self._app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

        # This will normalize all endpoints and strip any trailing '/'
        self._app.url_map.strict_slashes = False

        type_defs = load_schema_from_path(self.api.schema_path)
        object_types = {}

        LOG.debug("Using resolver list from API %s", self.api.resolvers)

        for resolver in self.api.resolvers:
            if resolver.object_type not in object_types:
                object_types[resolver.object_type] = ObjectType(resolver.object_type)

            object_types[resolver.object_type].set_field(resolver.field_name, self._generate_resolver(resolver))

        self.executable_schema = make_executable_schema(type_defs, *object_types.values())

        self._app.add_url_rule(
            "/graphql",
            endpoint="/graphql",
            view_func=self._request_handler,
            methods=["GET", "POST"],
            provide_automatic_options=False,
        )

    def _generate_resolver(self, resolver):
        def handler(_, info, **arguments):
            LOG.debug("Incoming request to LocalAppSyncService: %s.%s", info.parent_type.name, info.field_name)

            # LOG.info("Resolving field name %s, field nodes %s", info.field_name, pprint(vars(info)))
            LOG.info("Parent type is %s", info.parent_type.name)

            function_logical_id = resolver.function_name

            LOG.info("Function logical id = %s", function_logical_id)

            LOG.info("Resolving")

            LOG.info("Creating event %s", self._direct_lambda_resolver_event(arguments, info))

            return {"Hello": "world"}

        return handler

    def _direct_lambda_resolver_event(self, arguments, info):
        # @TODO select correct field_node based on info.field_name
        selection_set = [selection.name.value for selection in info.field_nodes[0].selection_set.selections]
        # @TODO get exact piece of the query that matches the field name
        selection_set_graphql = request.get_json()["query"]

        return {
            "arguments": arguments,
            "source": {},
            "identity": {},  # @todo fill with JWT token contents
            "request": {"headers": dict(request.headers)},
            "info": {
                "fieldName": info.field_name,
                "parentTypeName": info.parent_type.name,
                "variables": info.variable_values,
                "selectionSetList": selection_set,
                "selectionSetGraphQL": selection_set_graphql,
            },
        }

    def _graphql_playground(self):
        # On GET request serve GraphQL Playground
        return PLAYGROUND_HTML, 200

    def _request_handler(self):
        LOG.info("getting in req %s", request)

        if request.method == "GET":
            return self._graphql_playground()

        # GraphQL queries are always sent as POST
        data = request.get_json()

        # Note: Passing the request to the context is optional.
        # In Flask, the current request is always accessible as flask.request
        success, result = graphql_sync(
            self.executable_schema,
            data,
            context_value=request,
        )

        status_code = 200 if success else 400
        return jsonify(result), status_code

    # def _request_handler(self, **kwargs):
    #     """
    #     We handle all requests to the host:port. The general flow of handling a request is as follows

    #     * Fetch request from the Flask Global state. This is where Flask places the request and is per thread so
    #       multiple requests are still handled correctly
    #     * Find the Lambda function to invoke by doing a look up based on the request.endpoint and method
    #     * If we don't find the function, we will throw a 502 (just like the 404 and 405 responses we get
    #       from Flask.
    #     * Since we found a Lambda function to invoke, we construct the Lambda Event from the request
    #     * Then Invoke the Lambda function (docker container)
    #     * We then transform the response or errors we get from the Invoke and return the data back to
    #       the caller

    #     Parameters
    #     ----------
    #     kwargs dict
    #         Keyword Args that are passed to the function from Flask. This happens when we have path parameters

    #     Returns
    #     -------
    #     Response object
    #     """

    #     route = self._get_current_route(request)
    #     cors_headers = Cors.cors_to_headers(self.api.cors)

    #     method, endpoint = self.get_request_methods_endpoints(request)
    #     if method == "OPTIONS" and self.api.cors:
    #         headers = Headers(cors_headers)
    #         return self.service_response("", headers, 200)

    #     try:
    #         # the Lambda Event 2.0 is only used for the HTTP API gateway with defined payload format version equal 2.0
    #         # or none, as the default value to be used is 2.0
    #         # https://docs.aws.amazon.com/apigatewayv2/latest/api-reference/apis-apiid-integrations.html#apis-apiid-integrations-prop-createintegrationinput-payloadformatversion
    #         if route.event_type == Route.HTTP and route.payload_format_version in [None, "2.0"]:
    #             route_key = self._v2_route_key(method, endpoint, route.is_default_route)
    #             event = self._construct_v_2_0_event_http(
    #                 request,
    #                 self.port,
    #                 self.api.binary_media_types,
    #                 self.api.stage_name,
    #                 self.api.stage_variables,
    #                 route_key,
    #             )
    #         else:
    #             event = self._construct_v_1_0_event(
    #                 request, self.port, self.api.binary_media_types, self.api.stage_name, self.api.stage_variables
    #             )
    #     except UnicodeDecodeError:
    #         return ServiceErrorResponses.lambda_failure_response()

    #     stdout_stream = io.BytesIO()
    #     stdout_stream_writer = StreamWriter(stdout_stream, self.is_debugging)

    #     try:
    #         self.lambda_runner.invoke(route.function_name, event, stdout=stdout_stream_writer, stderr=self.stderr)
    #     except FunctionNotFound:
    #         return ServiceErrorResponses.lambda_not_found_response()

    #     lambda_response, lambda_logs, _ = LambdaOutputParser.get_lambda_output(stdout_stream)

    #     if self.stderr and lambda_logs:
    #         # Write the logs to stderr if available.
    #         self.stderr.write(lambda_logs)

    #     try:
    #         if route.event_type == Route.HTTP and (
    #             not route.payload_format_version or route.payload_format_version == "2.0"
    #         ):
    #             (status_code, headers, body) = self._parse_v2_payload_format_lambda_output(
    #                 lambda_response, self.api.binary_media_types, request
    #             )
    #         else:
    #             (status_code, headers, body) = self._parse_v1_payload_format_lambda_output(
    #                 lambda_response, self.api.binary_media_types, request
    #             )
    #     except LambdaResponseParseException as ex:
    #         LOG.error("Invalid lambda response received: %s", ex)
    #         return ServiceErrorResponses.lambda_failure_response()

    #     return self.service_response(body, headers, status_code)
