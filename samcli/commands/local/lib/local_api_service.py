"""
Connects the CLI with Local API Gateway service.
"""

import logging
import os

from samcli.commands.local.lib.exceptions import NoApisDefined
from samcli.lib.providers.api_provider import ApiProvider
from samcli.local.apigw.local_apigw_service import LocalApigwService

LOG = logging.getLogger(__name__)


class LocalApiService:
    """
    Implementation of Local API service that is capable of serving API defined in a configuration file that invoke a
    Lambda function.
    """

    def __init__(self, lambda_invoke_context, port, host, static_dir, disable_authorizer, ssl_context):
        """
        Initialize the local API service.

        :param samcli.commands.local.cli_common.invoke_context.InvokeContext lambda_invoke_context: Context object
            that can help with Lambda invocation
        :param int port: Port to listen on
        :param string host: Local hostname or IP address to bind to
        :param string static_dir: Optional, directory from which static files will be mounted
        :param bool disable_authorizer: Optional, flag for disabling the parsing of lambda authorizers
        :param tuple(string, string) ssl_context: Optional, path to ssl certificate and key files to start service
            in https
        """

        self.port = port
        self.host = host
        self.static_dir = static_dir
        self.ssl_context = ssl_context

        self.cwd = lambda_invoke_context.get_cwd()
        self.disable_authorizer = disable_authorizer
        self.api_provider = ApiProvider(
            lambda_invoke_context.stacks, cwd=self.cwd, disable_authorizer=disable_authorizer
        )
        self.lambda_runner = lambda_invoke_context.local_lambda_runner
        self.stderr_stream = lambda_invoke_context.stderr

    def start(self):
        """
        Creates and starts the local API Gateway service. This method will block until the service is stopped
        manually using an interrupt. After the service is started, callers can make HTTP requests to the endpoint
        to invoke the Lambda function and receive a response.

        NOTE: This is a blocking call that will not return until the thread is interrupted with SIGINT/SIGTERM
        """

        if not self.api_provider.api.routes:
            raise NoApisDefined("No APIs available in template")

        static_dir_path = self._make_static_dir_path(self.cwd, self.static_dir)

        # We care about passing only stderr to the Service and not stdout because stdout from Docker container
        # contains the response to the API which is sent out as HTTP response. Only stderr needs to be printed
        # to the console or a log file. stderr from Docker container contains runtime logs and output of print
        # statements from the Lambda function
        service = LocalApigwService(
            api=self.api_provider.api,
            lambda_runner=self.lambda_runner,
            static_dir=static_dir_path,
            port=self.port,
            host=self.host,
            ssl_context=self.ssl_context,
            stderr=self.stderr_stream,
        )

        service.create()

        # Print out the list of routes that will be mounted
        self._print_routes(self.api_provider.api.routes, self.host, self.port, bool(self.ssl_context))
        LOG.info(
            "You can now browse to the above endpoints to invoke your functions. "
            "You do not need to restart/reload SAM CLI while working on your functions, "
            "changes will be reflected instantly/automatically. If you used sam build before "
            "running local commands, you will need to re-run sam build for the changes "
            "to be picked up. You only need to restart SAM CLI if you update your AWS SAM template"
        )

        service.run()

    @staticmethod
    def _print_routes(routes, host, port, ssl_enabled=False):
        """
        Helper method to print the APIs that will be mounted. This method is purely for printing purposes.
        This method takes in a list of Route Configurations and prints out the Routes grouped by path.
        Grouping routes by Function Name + Path is the bulk of the logic.

        Example output:
            Mounting Product at http://127.0.0.1:3000/path1/bar [GET, POST, DELETE]
            Mounting Product at http://127.0.0.1:3000/path2/bar [HEAD]

        :param list(Route) routes:
            List of routes grouped by the same function_name and path
        :param string host:
            Host name where the service is running
        :param int port:
            Port number where the service is running
        :param bool ssl_enabled:
            Boolean parameter to set whether SSL configuration is enabled
        :returns list(string):
            List of lines that were printed to the console. Helps with testing
        """

        print_lines = []
        protocol = "https" if ssl_enabled else "http"
        for route in routes:
            methods_str = "[{}]".format(", ".join(route.methods))
            output = "Mounting {} at {}://{}:{}{} {}".format(
                route.function_name, protocol, host, port, route.path, methods_str
            )
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
