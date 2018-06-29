"""Local Lambda Service that only invokes a function"""

import logging
import io

from flask import Flask, request


from samcli.local.services.localhost_runner import LocalhostRunner, LambdaOutputParser
from samcli.local.lambdafn.exceptions import FunctionNotFound

LOG = logging.getLogger(__name__)


class LocalInvoke(LocalhostRunner):

    def __init__(self, lambda_runner, port, host, stderr=None):
        """
        Creates a Local Lambda Service that will only response to invoking a function

        Parameters
        ----------
        lambda_runner samcli.commands.local.lib.local_lambda.LocalLambdaRunner
            The Lambda runner class capable of invoking the function
        port int
            Optional. port for the service to start listening on
        host str
            Optional. host to start the service on
        stderr io.BaseIO
            Optional stream where the stderr from Docker container should be written to
        """
        super(LocalInvoke, self).__init__(lambda_runner, port=port, host=host, stderr=stderr)

    def create(self):
        """
        Creates a Flask Application that can be started.
        """
        self._app = Flask(__name__)

        path = '/2015-03-31/functions/<function_name>/invocations'
        self._app.add_url_rule(path,
                               endpoint=path,
                               view_func=self._invoke_request_handler,
                               methods=['POST'],
                               provide_automatic_options=False)

        self._construct_error_handling()

    def _construct_error_handling(self):
        """
        Updates the Flask app with Error Handlers for different Error Codes

        """
        pass

    def _invoke_request_handler(self, function_name):
        """
        Request Handler for the Local Lambda Invoke path. This method is responsible for understanding the incoming
        request and invoking the Local Lambda Function

        Parameters
        ----------
        function_name str
            Name of the function to invoke

        Returns
        -------
        A Flask Response response object as if it was returned from Lambda

        """
        flask_request = request
        request_data = flask_request.get_data().decode('utf-8')

        stdout_stream = io.BytesIO()

        try:
            self.lambda_runner.invoke(function_name, request_data, stdout=stdout_stream, stderr=self.stderr)
        except FunctionNotFound:
            # TODO Change this
            raise Exception('Change this later')

        lambda_response, lambda_logs = LambdaOutputParser.get_lambda_output(stdout_stream)

        if self.stderr and lambda_logs:
            # Write the logs to stderr if available.
            self.stderr.write(lambda_logs)

        return self._service_response(lambda_response, {'Content-Type': 'application/json'}, 200)
