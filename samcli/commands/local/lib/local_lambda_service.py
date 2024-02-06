"""
Connects the CLI with Local Lambda Invoke Service.
"""

import logging

from samcli.local.lambda_service.local_lambda_invoke_service import LocalLambdaInvokeService

LOG = logging.getLogger(__name__)


class LocalLambdaService:
    """
    Implementation of Local Lambda Invoke Service that is capable of serving the invoke path to your Lambda Functions
    that are defined in a SAM file.
    """

    def __init__(self, lambda_invoke_context, port, host, ssl_context=None):
        """
        Initialize the Local Lambda Invoke service.

        :param samcli.commands.local.cli_common.invoke_context.InvokeContext lambda_invoke_context: Context object
            that can help with Lambda invocation
        :param int port: Port to listen on
        :param string host: Local hostname or IP address to bind to
        :param tuple(string, string) ssl_context: Optional, path to ssl certificate and key files to start service
            in https
        """

        self.port = port
        self.host = host
        self.ssl_context = ssl_context
        self.lambda_runner = lambda_invoke_context.local_lambda_runner
        self.stderr_stream = lambda_invoke_context.stderr

    def start(self):
        """
        Creates and starts the Local Lambda Invoke service. This method will block until the service is stopped
        manually using an interrupt. After the service is started, callers can make HTTP requests to the endpoint
        to invoke the Lambda function and receive a response.

        NOTE: This is a blocking call that will not return until the thread is interrupted with SIGINT/SIGTERM
        """

        # We care about passing only stderr to the Service and not stdout because stdout from Docker container
        # contains the response to the API which is sent out as HTTP response. Only stderr needs to be printed
        # to the console or a log file. stderr from Docker container contains runtime logs and output of print
        # statements from the Lambda function
        service = LocalLambdaInvokeService(
            lambda_runner=self.lambda_runner,
            port=self.port,
            host=self.host,
            ssl_context=self.ssl_context,
            stderr=self.stderr_stream,
        )

        service.create()

        LOG.info(
            "Starting the Local Lambda Service. You can now invoke your Lambda Functions defined in your template"
            " through the endpoint."
        )

        service.run()
