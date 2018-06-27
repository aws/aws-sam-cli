"""Local Lambda Service"""

import logging
import re
import io
import os

from flask import Flask, jsonify, request, Response


from samcli.local.services.base_service import BaseService
from samcli.local.lambdafn.exceptions import FunctionNotFound

LOG = logging.getLogger(__name__)


class LocalLambdaService(BaseService):

    _DEFAULT_PORT = 3001
    _DEFAULT_HOST = '127.0.0.1'

    def __init__(self, function_name_list, lambda_runner, port=None, host=None, stderr=None):
        """
        Creates a Local Lambda Service

        Parameters
        ----------
        function_name_list list of str
            List of the Function Logical Ids
        lambda_runner samcli.commands.local.lib.local_lambda.LocalLambdaRunner
            The Lambda runner class capable of invoking the function
        port int
            Optional. port for the service to start listening on. Defaults to 3001
        host str
            Optional. host to start the service on Defaults to '127.0.0.1'
        stderr io.BaseIO
            Optional stream where the stderr from Docker container should be written to
        """
        self.function_name_list = function_name_list
        super(LocalLambdaService, self).__init__(lambda_runner, port=port, host=host, stderr=stderr)

    def create(self):
        """
        Creates a Flask Application that can be started.
        """
        self._app = Flask(__name__)

        for function_name in self.function_name_list:
            path = '/2015-03-31/functions/{}/invocations'.format(function_name)
            self._app.add_url_rule(path,
                                   endpoint=path,
                                   view_func=self._invoke_request_handler,
                                   methods=['POST'],
                                   provide_automatic_options=False)

        self._construct_error_handling()

    def run(self):
        """
        This starts up the (threaded) Local Server.
        Note: This is a **blocking call**

        Raises
        ------
        RuntimeError
            if the service was not created
        """
        if not self._app:
            raise RuntimeError("The application must be created before running")

        # Flask can operate as a single threaded server (which is default) and a multi-threaded server which is
        # more for development. When the Lambda container is going to be debugged, then it does not make sense
        # to turn on multi-threading because customers can realistically attach only one container at a time to
        # the debugger. Keeping this single threaded also enables the Lambda Runner to handle Ctrl+C in order to
        # kill the container gracefully (Ctrl+C can be handled only by the main thread)
        multi_threaded = not self.lambda_runner.is_debugging()

        LOG.debug("Local Lambda Server starting up. Multi-threading = %s", multi_threaded)

        # This environ signifies we are running a main function for Flask. This is true, since we are using it within
        # our cli and not on a production server.
        os.environ['WERKZEUG_RUN_MAIN'] = 'true'

        self._app.run(threaded=multi_threaded, host=self.host, port=self.port)

    def _construct_error_handling(self):
        """
        Updates the Flask app with Error Handlers for different Error Codes

        """
        pass

    def _invoke_request_handler(self):
        """
        Request Handler for the Local Lambda Invoke path. This method is responsible for understanding the incoming
        request and invoking the Local Lambda Function

        Returns
        -------
        A Flask Response response object as if it was returned from Lambda

        """
        flask_request = request

        function_name_regex = re.compile(r'/2015-03-31/functions/(.*)/invocations')

        regex_match = function_name_regex.match(request.path)

        function_name = ""

        if regex_match:
           function_name = regex_match.group(1)

        stdout_stream = io.BytesIO()

        try:
            self.lambda_runner.invoke(function_name, {}, stdout=stdout_stream, stderr=self.stderr)
        except FunctionNotFound:
            # TODO Change this
            raise Exception('Change this later')

        lambda_response, lambda_logs = self._get_lambda_output(stdout_stream)

        # import pdb; pdb.set_trace()

        if self.stderr and lambda_logs:
            # Write the logs to stderr if available.
            self.stderr.write(lambda_logs)

        return self._service_response(lambda_response, {'Content-Type': 'application/json'}, 200)
