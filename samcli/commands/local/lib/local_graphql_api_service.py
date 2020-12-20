"""
Connects the CLI with Local API Gateway service.
"""

import logging
import os

from samcli.commands.local.lib.exceptions import NoApisDefined
from samcli.local.appsync.local_appsync_service import LocalAppSyncService
from samcli.lib.providers.graphql_api_provider import GraphQLApiProvider

LOG = logging.getLogger(__name__)


class LocalGraphQLApiService:
    """
    Implementation of Local API service that is capable of serving API defined in a configuration file that invoke a
    Lambda function.
    """

    def __init__(self, lambda_invoke_context, port, host, static_dir):
        """
        Initialize the local API service.

        :param samcli.commands.local.cli_common.invoke_context.InvokeContext lambda_invoke_context: Context object
            that can help with Lambda invocation
        :param int port: Port to listen on
        :param string host: Local hostname or IP address to bind to
        :param string static_dir: Optional, directory from which static files will be mounted
        """

        self.port = port
        self.host = host
        self.static_dir = static_dir

        self.cwd = lambda_invoke_context.get_cwd()
        self.api_provider = GraphQLApiProvider(
            lambda_invoke_context.template, parameter_overrides=lambda_invoke_context.parameter_overrides, cwd=self.cwd
        )
        self.lambda_runner = lambda_invoke_context.local_lambda_runner
        self.stderr_stream = lambda_invoke_context.stderr

    def start(self):
        """
        Creates and starts the local AppSync service. This method will block until the service is stopped
        manually using an interrupt. After the service is started, callers can make HTTP requests to the endpoint
        to invoke the Lambda function and receive a response.

        NOTE: This is a blocking call that will not return until the thread is interrupted with SIGINT/SIGTERM
        """

        if not self.api_provider.api.resolvers:
            raise NoApisDefined("No APIs available in template")

        static_dir_path = self._make_static_dir_path(self.cwd, self.static_dir)

        # We care about passing only stderr to the Service and not stdout because stdout from Docker container
        # contains the response to the API which is sent out as HTTP response. Only stderr needs to be printed
        # to the console or a log file. stderr from Docker container contains runtime logs and output of print
        # statements from the Lambda function
        service = LocalAppSyncService(
            api=self.api_provider.api,
            lambda_runner=self.lambda_runner,
            static_dir=static_dir_path,
            port=self.port,
            host=self.host,
            stderr=self.stderr_stream,
        )

        service.create()

        # Print out the list of routes that will be mounted
        self._print_resolvers(self.api_provider.api.resolvers, self.host, self.port)
        LOG.info(
            "You can now browse to the above endpoints to invoke your functions. "
            "You do not need to restart/reload SAM CLI while working on your functions, "
            "changes will be reflected instantly/automatically. You only need to restart "
            "SAM CLI if you update your AWS SAM template"
        )

        service.run()

    @staticmethod
    def _print_resolvers(resolvers, host, port):
        """
        Helper method to print the APIs that will be mounted. This method is purely for printing purposes.
        This method takes in a list of Resolvers and prints out them.

        Example output:
            Mounting GraphQL endpoint at http://127.0.0.1:3000/graphql [POST]
            Mounting GraphQL playground at http://127.0.0.1:3000/graphql [GET]

        :param list(Route) routes:
            List of routes grouped by the same function_name and path
        :param string host:
            Host name where the service is running
        :param int port:
            Port number where the service is running
        :returns list(string):
            List of lines that were printed to the console. Helps with testing
        """

        print_lines = []
        mounted_endpoints = {
            "endpoint": "POST",
            "playground": "GET",
        }

        for name, method in mounted_endpoints.items():
            output = f"Mounting GraphQL {name} at http://{host}:{port}/graphql [{method}]"

            print_lines.append(output)
            LOG.info(output)

        for resolver in resolvers:
            output = f"Resolving {resolver.object_type}.{resolver.field_name} using Lambda {resolver.function_name}"

            print_lines.append(output)
            LOG.info(output)

        return print_lines

    @staticmethod
    def _make_static_dir_path(cwd, static_dir):
        """
        This method returns the path to the directory where static files are to be served from. If static_dir is a
        relative path, then it is resolved to be relative to the current working directory. If no static directory is
        provided, or if the resolved directory does not exist, this method will return None

        :param string cwd: Current working directory relative to which we will resolve the static directory
        :param string static_dir: Path to the static directory
        :return string: Path to the static directory, if it exists. None, otherwise
        """
        if not static_dir:
            return None

        static_dir_path = os.path.join(cwd, static_dir)
        if os.path.exists(static_dir_path):
            LOG.info("Mounting static files from %s at /", static_dir_path)
            return static_dir_path

        return None
