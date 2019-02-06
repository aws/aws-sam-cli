"""
Connects the CLI with Local API Gateway service.
"""

import os
import logging

from samcli.local.apigw.local_apigw_service import LocalApigwService, Route
from samcli.commands.local.lib.sam_api_provider import SamApiProvider
from samcli.commands.local.lib.exceptions import NoApisDefined

LOG = logging.getLogger(__name__)


class LocalApiService(object):
    """
    Implementation of Local API service that is capable of serving APIs defined in a SAM file that invoke a Lambda
    function.
    """

    def __init__(self,
                 lambda_invoke_context,
                 port,
                 host,
                 static_dir):
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
        self.api_provider = SamApiProvider(lambda_invoke_context.template,
                                           parameter_overrides=lambda_invoke_context.parameter_overrides,
                                           cwd=self.cwd)
        self.lambda_runner = lambda_invoke_context.local_lambda_runner
        self.stderr_stream = lambda_invoke_context.stderr

    def start(self):
        """
        Creates and starts the local API Gateway service. This method will block until the service is stopped
        manually using an interrupt. After the service is started, callers can make HTTP requests to the endpoint
        to invoke the Lambda function and receive a response.

        NOTE: This is a blocking call that will not return until the thread is interrupted with SIGINT/SIGTERM
        """

        routing_list = self._make_routing_list(self.api_provider)

        if not routing_list:
            raise NoApisDefined("No APIs available in SAM template")

        static_dir_path = self._make_static_dir_path(self.cwd, self.static_dir)

        # We care about passing only stderr to the Service and not stdout because stdout from Docker container
        # contains the response to the API which is sent out as HTTP response. Only stderr needs to be printed
        # to the console or a log file. stderr from Docker container contains runtime logs and output of print
        # statements from the Lambda function
        service = LocalApigwService(routing_list=routing_list,
                                    lambda_runner=self.lambda_runner,
                                    static_dir=static_dir_path,
                                    port=self.port,
                                    host=self.host,
                                    stderr=self.stderr_stream)

        service.create()

        # Print out the list of routes that will be mounted
        self._print_routes(self.api_provider, self.host, self.port)
        LOG.info("You can now browse to the above endpoints to invoke your functions. "
                 "You do not need to restart/reload SAM CLI while working on your functions, "
                 "changes will be reflected instantly/automatically. You only need to restart "
                 "SAM CLI if you update your AWS SAM template")

        service.run()

    @staticmethod
    def _make_routing_list(api_provider):
        """
        Returns a list of routes to configure the Local API Service based on the APIs configured in the template.

        Parameters
        ----------
        api_provider : samcli.commands.local.lib.sam_api_provider.SamApiProvider

        Returns
        -------
        list(samcli.local.apigw.service.Route)
            List of Routes to pass to the service
        """

        routes = []
        for api in api_provider.get_all():
            route = Route(methods=[api.method], function_name=api.function_name, path=api.path,
                          binary_types=api.binary_media_types)
            routes.append(route)

        return routes

    @staticmethod
    def _print_routes(api_provider, host, port):
        """
        Helper method to print the APIs that will be mounted. This method is purely for printing purposes.
        This method takes in a list of Route Configurations and prints out the Routes grouped by path.
        Grouping routes by Function Name + Path is the bulk of the logic.

        Example output:
            Mounting Product at http://127.0.0.1:3000/path1/bar [GET, POST, DELETE]
            Mounting Product at http://127.0.0.1:3000/path2/bar [HEAD]

        :param samcli.commands.local.lib.provider.ApiProvider api_provider: API Provider that can return a list of APIs
        :param string host: Host name where the service is running
        :param int port: Port number where the service is running
        :returns list(string): List of lines that were printed to the console. Helps with testing
        """
        grouped_api_configs = {}

        for api in api_provider.get_all():
            key = "{}-{}".format(api.function_name, api.path)

            config = grouped_api_configs.get(key, {})
            config.setdefault("methods", [])

            config["function_name"] = api.function_name
            config["path"] = api.path
            config["methods"].append(api.method)

            grouped_api_configs[key] = config

        print_lines = []
        for _, config in grouped_api_configs.items():
            methods_str = "[{}]".format(', '.join(config["methods"]))
            output = "Mounting {} at http://{}:{}{} {}".format(
                         config["function_name"],
                         host,
                         port,
                         config["path"],
                         methods_str)
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
