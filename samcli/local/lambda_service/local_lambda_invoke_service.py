"""Local Lambda Service that only invokes a function"""

import json
import logging
import io

from flask import Flask, request


from samcli.local.services.base_local_service import BaseLocalService, LambdaOutputParser
from samcli.local.lambdafn.exceptions import FunctionNotFound
from .lambda_error_responses import LambdaErrorResponses

LOG = logging.getLogger(__name__)


class LocalLambdaInvokeService(BaseLocalService):

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
        super(LocalLambdaInvokeService, self).__init__(lambda_runner.is_debugging(), port=port, host=host)
        self.lambda_runner = lambda_runner
        self.stderr = stderr

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

        # setup request validation before Flask calls the view_func
        self._app.before_request = self.validate_request

        self._construct_error_handling()

    def validate_request(self):
        """
        Validates the incoming request

        Returns
        -------
        flask.Response
            A Response is returned in the following cases:
            1. The Request data is not json serializable
            2. Query Parameters are sent to the endpoint
            3. The Request Content-Type is not application/json

            Otherwise this function does not return anything
        """
        flask_request = request
        request_data = flask_request.get_data()

        if not request_data:
            request_data = b'{}'

        request_data = request_data.decode('utf-8')

        try:
            json.loads(request_data)
        except ValueError as json_error:
            LOG.debug("Request body was not json.")
            return LambdaErrorResponses.invalid_request_content(
                "Could not parse request body into json: {}".format(str(json_error)))

        if flask_request.args:
            LOG.debug("Query parameters are in the request but not supported")
            return LambdaErrorResponses.invalid_request_content("Query Parameters are not supported")

        if flask_request.content_type.lower() != "application/json":
            LOG.debug("%s media type is not supported. Must be application/json", flask_request.content_type)
            return LambdaErrorResponses.unsupported_media_type(flask_request.content_type)

        log_type = flask_request.headers.get('X-Amz-Log-Type', 'None')
        if log_type != 'None':
            LOG.info("log-type: %s is not supported. Ignoring X-Amz-Log-Type header", log_type)

        invocation_type = flask_request.headers.get('X-Amz-Invocation-Type', 'RequestResponse')
        if invocation_type != 'RequestResponse':
            LOG.warning("invocation_type: %s is not supported. RequestResponse is only supported.", invocation_type)
            return LambdaErrorResponses.not_implemented_locally(
                "invocation_type: {} is not supported. RequestResponse is only supported.".format(invocation_type))

    def _construct_error_handling(self):
        """
        Updates the Flask app with Error Handlers for different Error Codes

        """
        self._app.register_error_handler(500, LambdaErrorResponses.generic_service_exception())
        self._app.register_error_handler(404, LambdaErrorResponses.resource_not_found(""))

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

        request_data = flask_request.get_data()

        if not request_data:
            request_data = b'{}'

        request_data = request_data.decode('utf-8')

        stdout_stream = io.BytesIO()

        try:
            self.lambda_runner.invoke(function_name, request_data, stdout=stdout_stream, stderr=self.stderr)
        except FunctionNotFound:
            LOG.debug('%s was not found to invoke.', function_name)
            return LambdaErrorResponses.resource_not_found(function_name)

        lambda_response, lambda_logs, is_lambda_user_error_response = \
            LambdaOutputParser.get_lambda_output(stdout_stream)

        if is_lambda_user_error_response:
            return self._service_response(lambda_response,
                                          {'Content-Type': 'application/json', 'x-amz-function-error': 'Unhandled'},
                                          200)

        if self.stderr and lambda_logs:
            # Write the logs to stderr if available.
            self.stderr.write(lambda_logs)

        return self._service_response(lambda_response, {'Content-Type': 'application/json'}, 200)
