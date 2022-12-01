"""Local Lambda Service that only invokes a function"""

import json
import logging
import io

from flask import Flask, request
from werkzeug.routing import BaseConverter

from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.services.base_local_service import BaseLocalService, LambdaOutputParser
from samcli.local.lambdafn.exceptions import FunctionNotFound
from .lambda_error_responses import LambdaErrorResponses

LOG = logging.getLogger(__name__)


class FunctionNamePathConverter(BaseConverter):
    regex = ".+"

    def to_python(self, value):  # type: ignore[no-untyped-def]
        return value

    def to_url(self, value):  # type: ignore[no-untyped-def]
        return value


class LocalLambdaInvokeService(BaseLocalService):
    def __init__(self, lambda_runner, port, host, stderr=None):  # type: ignore[no-untyped-def]
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
        super().__init__(lambda_runner.is_debugging(), port=port, host=host)  # type: ignore[no-untyped-call]
        self.lambda_runner = lambda_runner
        self.stderr = stderr

    def create(self):  # type: ignore[no-untyped-def]
        """
        Creates a Flask Application that can be started.
        """
        self._app = Flask(__name__)

        # add converter to support nested stack function path
        self._app.url_map.converters["function_path"] = FunctionNamePathConverter

        path = "/2015-03-31/functions/<function_path:function_name>/invocations"
        self._app.add_url_rule(
            path,
            endpoint=path,
            view_func=self._invoke_request_handler,
            methods=["POST"],
            provide_automatic_options=False,
        )

        # setup request validation before Flask calls the view_func
        self._app.before_request(LocalLambdaInvokeService.validate_request)

        self._construct_error_handling()  # type: ignore[no-untyped-call]

    @staticmethod
    def validate_request():  # type: ignore[no-untyped-def]
        """
        Validates the incoming request

        The following are invalid
            1. The Request data is not json serializable
            2. Query Parameters are sent to the endpoint
            3. The Request Content-Type is not application/json
            4. 'X-Amz-Log-Type' header is not 'None'
            5. 'X-Amz-Invocation-Type' header is not 'RequestResponse'

        Returns
        -------
        flask.Response
            If the request is not valid a flask Response is returned

        None:
            If the request passes all validation
        """
        flask_request = request
        request_data = flask_request.get_data()

        if not request_data:
            request_data = b"{}"

        request_data = request_data.decode("utf-8")  # type: ignore[assignment]

        try:
            json.loads(request_data)
        except ValueError as json_error:
            LOG.debug("Request body was not json. Exception: %s", str(json_error))
            return LambdaErrorResponses.invalid_request_content(  # type: ignore[no-untyped-call]
                "Could not parse request body into json: No JSON object could be decoded"
            )

        if flask_request.args:
            LOG.debug("Query parameters are in the request but not supported")
            return LambdaErrorResponses.invalid_request_content("Query Parameters are not supported")  # type: ignore[no-untyped-call]

        request_headers = flask_request.headers

        log_type = request_headers.get("X-Amz-Log-Type", "None")
        if log_type != "None":
            LOG.debug("log-type: %s is not supported. None is only supported.", log_type)
            return LambdaErrorResponses.not_implemented_locally(  # type: ignore[no-untyped-call]
                "log-type: {} is not supported. None is only supported.".format(log_type)
            )

        invocation_type = request_headers.get("X-Amz-Invocation-Type", "RequestResponse")
        if invocation_type != "RequestResponse":
            LOG.warning("invocation-type: %s is not supported. RequestResponse is only supported.", invocation_type)
            return LambdaErrorResponses.not_implemented_locally(  # type: ignore[no-untyped-call]
                "invocation-type: {} is not supported. RequestResponse is only supported.".format(invocation_type)
            )

        return None

    def _construct_error_handling(self):  # type: ignore[no-untyped-def]
        """
        Updates the Flask app with Error Handlers for different Error Codes

        """
        self._app.register_error_handler(500, LambdaErrorResponses.generic_service_exception)  # type: ignore[union-attr]
        self._app.register_error_handler(404, LambdaErrorResponses.generic_path_not_found)  # type: ignore[union-attr]
        self._app.register_error_handler(405, LambdaErrorResponses.generic_method_not_allowed)  # type: ignore[union-attr]

    def _invoke_request_handler(self, function_name):  # type: ignore[no-untyped-def]
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
            request_data = b"{}"

        request_data = request_data.decode("utf-8")  # type: ignore[assignment]

        stdout_stream = io.BytesIO()
        stdout_stream_writer = StreamWriter(stdout_stream, auto_flush=True)  # type: ignore[no-untyped-call]

        try:
            self.lambda_runner.invoke(function_name, request_data, stdout=stdout_stream_writer, stderr=self.stderr)
        except FunctionNotFound:
            LOG.debug("%s was not found to invoke.", function_name)
            return LambdaErrorResponses.resource_not_found(function_name)  # type: ignore[no-untyped-call]

        lambda_response, lambda_logs, is_lambda_user_error_response = LambdaOutputParser.get_lambda_output(  # type: ignore[no-untyped-call]
            stdout_stream
        )

        if self.stderr and lambda_logs:
            # Write the logs to stderr if available.
            self.stderr.write(lambda_logs)

        if is_lambda_user_error_response:
            return self.service_response(  # type: ignore[no-untyped-call]
                lambda_response, {"Content-Type": "application/json", "x-amz-function-error": "Unhandled"}, 200
            )

        return self.service_response(lambda_response, {"Content-Type": "application/json"}, 200)  # type: ignore[no-untyped-call]
