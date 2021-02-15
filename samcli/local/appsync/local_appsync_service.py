"""AppSync Local Service"""
import io
import json
import logging

from flask import Flask, request, jsonify
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

            object_types[resolver.object_type].set_field(resolver.field_name, self._generate_resolver_fn(resolver))

        self.executable_schema = make_executable_schema(type_defs, *object_types.values())

        self._app.add_url_rule(
            "/graphql",
            endpoint="/graphql",
            view_func=self._request_handler,
            methods=["GET", "POST"],
            provide_automatic_options=False,
        )

    def _generate_resolver_fn(self, resolver):
        def handler(_, info, **arguments):
            LOG.debug("Incoming request to LocalAppSyncService: %s.%s", info.parent_type.name, info.field_name)

            event = self._direct_lambda_resolver_event(request, arguments, info)

            LOG.debug("Generated direct Lambda resolver event %s", event)

            stdout_stream = io.BytesIO()
            stdout_stream_writer = StreamWriter(stdout_stream, self.is_debugging)

            try:
                self.lambda_runner.invoke(
                    resolver.function_name, event, stdout=stdout_stream_writer, stderr=self.stderr
                )
            except FunctionNotFound:
                return {"errors": "Lambda not found"}

            LOG.info("Stdout stream info %s", stdout_stream)

            lambda_response, lambda_logs, _ = LambdaOutputParser.get_lambda_output(stdout_stream)

            if self.stderr and lambda_logs:
                # Write the logs to stderr if available.
                self.stderr.write(lambda_logs)

            LOG.info("Lambda response %s", lambda_response)

            return json.loads(lambda_response)

        return handler

    @staticmethod
    def _direct_lambda_resolver_event(req, arguments, info):
        # @TODO select correct field_node based on info.field_name
        selection_set = [selection.name.value for selection in info.field_nodes[0].selection_set.selections]
        # @TODO get exact piece of the query that matches the field name
        selection_set_graphql = req.get_json()["query"]

        contents = {
            "arguments": arguments,
            "source": {},
            "identity": {},  # @todo fill with JWT token contents
            "request": {"headers": dict(req.headers)},
            "info": {
                "fieldName": info.field_name,
                "parentTypeName": info.parent_type.name,
                "variables": info.variable_values,
                "selectionSetList": selection_set,
                "selectionSetGraphQL": selection_set_graphql,
            },
        }

        return json.dumps(contents)

    def _request_handler(self):
        LOG.info("getting in req %s", request)

        if request.method == "GET":
            return graphql_playground()

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


def graphql_playground():
    # On GET request serve GraphQL Playground
    return PLAYGROUND_HTML, 200
