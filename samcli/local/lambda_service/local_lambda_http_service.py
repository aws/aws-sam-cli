"""Local Lambda Service that handles a subset of lambda APIs: Invoke, GetDurableExecution, GetDurableExecutionHistory"""

import io
import json
import logging
from datetime import datetime
from urllib.parse import unquote

from flask import Flask, request
from werkzeug.routing import BaseConverter

from samcli.commands.local.cli_common.durable_context import DurableContext
from samcli.commands.local.lib.exceptions import TenantIdValidationError, UnsupportedInlineCodeError
from samcli.lib.utils.name_utils import InvalidFunctionNameException, normalize_sam_function_identifier
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.docker.exceptions import DockerContainerCreationFailedException
from samcli.local.lambdafn.exceptions import DurableExecutionNotFound, FunctionNotFound, UnsupportedInvocationType
from samcli.local.services.base_local_service import BaseLocalService, LambdaOutputParser

from .lambda_error_responses import LambdaErrorResponses

LOG = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects"""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.timestamp()
        return super().default(obj)


class FunctionNamePathConverter(BaseConverter):
    regex = ".+"
    weight = 300
    part_isolating = False

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


class LocalLambdaHttpService(BaseLocalService):
    INVOKE_ENDPOINT = "/2015-03-31/functions/<function_path:function_name>/invocations"

    def __init__(self, lambda_runner, port, host, stderr=None, ssl_context=None):
        """
        Creates a Local Lambda Service that handles both regular invocations and durable functions

        Parameters
        ----------
        lambda_runner samcli.commands.local.lib.local_lambda.LocalLambdaRunner
            The Lambda runner class capable of invoking the function
        port int
            Optional. port for the service to start listening on
        host str
            Optional. host to start the service on
        ssl_context : (str, str)
            Optional. tuple(str, str) indicating the cert and key files to use to start in https mode
            Defaults to None
        stderr io.BaseIO
            Optional stream where the stderr from Docker container should be written to
        """
        super().__init__(lambda_runner.is_debugging(), port=port, host=host, ssl_context=ssl_context)
        self.lambda_runner = lambda_runner
        self.stderr = stderr

    def create(self):
        """
        Creates a Flask Application that can be started.
        """
        self._app = Flask(__name__)

        # add converter to support nested stack function path
        self._app.url_map.converters["function_path"] = FunctionNamePathConverter

        # Lambda invocation endpoint
        self._app.add_url_rule(
            self.INVOKE_ENDPOINT,
            endpoint=self.INVOKE_ENDPOINT,
            view_func=self._invoke_request_handler,
            methods=["POST"],
            provide_automatic_options=False,
        )

        # Durable functions endpoints
        self._app.add_url_rule(
            "/2025-12-01/durable-executions/<durable_execution_arn>",
            endpoint="get_durable_execution",
            view_func=self._get_durable_execution_handler,
            methods=["GET"],
        )

        self._app.add_url_rule(
            "/2025-12-01/durable-executions/<durable_execution_arn>/history",
            endpoint="get_durable_execution_history",
            view_func=self._get_durable_execution_history_handler,
            methods=["GET"],
        )

        self._app.add_url_rule(
            "/2025-12-01/durable-executions/<durable_execution_arn>/stop",
            endpoint="stop_durable_execution",
            view_func=self._stop_durable_execution_handler,
            methods=["POST"],
        )

        # Callback endpoints
        self._app.add_url_rule(
            "/2025-12-01/durable-execution-callbacks/<callback_id>/succeed",
            endpoint="send_callback_success",
            view_func=self._send_callback_success_handler,
            methods=["POST"],
        )

        self._app.add_url_rule(
            "/2025-12-01/durable-execution-callbacks/<callback_id>/fail",
            endpoint="send_callback_failure",
            view_func=self._send_callback_failure_handler,
            methods=["POST"],
        )

        self._app.add_url_rule(
            "/2025-12-01/durable-execution-callbacks/<callback_id>/heartbeat",
            endpoint="send_callback_heartbeat",
            view_func=self._send_callback_heartbeat_handler,
            methods=["POST"],
        )

        # setup request validation before Flask calls the view_func
        self._app.before_request(LocalLambdaHttpService.validate_request)

        self._construct_error_handling()

    @staticmethod
    def validate_request():
        """
        Validates incoming requests based on the endpoint

        For invoke endpoints, performs specific validation checks.
        Other endpoints pass through without validation.
        """
        if request.endpoint == LocalLambdaHttpService.INVOKE_ENDPOINT:
            return LocalLambdaHttpService._validate_invoke_request(request)
        return None

    @staticmethod
    def _validate_invoke_request(flask_request):
        """
        Validates the incoming invoke request specifically

        The following are invalid for invoke requests:
            1. The Request data is not json serializable
            2. Query Parameters are sent to the endpoint
            3. The Request Content-Type is not application/json
            4. 'X-Amz-Log-Type' header is not 'None'
            5. 'X-Amz-Invocation-Type' header is not 'RequestResponse'

        Args:
            flask_request: The Flask request object to validate

        Returns
        -------
        flask.Response
            If the request is not valid a flask Response is returned

        None:
            If the request passes all validation
        """
        request_data = flask_request.get_data()

        if not request_data:
            request_data = b"{}"

        request_data = request_data.decode("utf-8")

        try:
            json.loads(request_data)
        except ValueError as json_error:
            LOG.debug("Request body was not json. Exception: %s", str(json_error))
            return LambdaErrorResponses.invalid_request_content(
                "Could not parse request body into json: No JSON object could be decoded"
            )

        if flask_request.args:
            LOG.debug("Query parameters are in the request but not supported for invoke endpoint")
            return LambdaErrorResponses.invalid_request_content("Query Parameters are not supported")

        request_headers = flask_request.headers

        log_type = request_headers.get("X-Amz-Log-Type", "None")
        if log_type != "None":
            LOG.debug("log-type: %s is not supported. None is only supported.", log_type)
            return LambdaErrorResponses.not_implemented_locally(
                "log-type: {} is not supported. None is only supported.".format(log_type)
            )

        return None

    def _construct_error_handling(self):
        """
        Updates the Flask app with Error Handlers for different Error Codes

        """
        self._app.register_error_handler(500, LambdaErrorResponses.generic_service_exception)
        self._app.register_error_handler(404, LambdaErrorResponses.generic_path_not_found)
        self._app.register_error_handler(405, LambdaErrorResponses.generic_method_not_allowed)

    def _invoke_request_handler(self, function_name):
        """
        Request Handler for the Local Lambda Invoke path. This method is responsible for understanding the incoming
        request and invoking the Local Lambda Function

        Parameters
        ----------
        function_name str
            Name or ARN of the function to invoke

        Returns
        -------
        A Flask Response response object as if it was returned from Lambda
        """
        flask_request = request
        request_data = flask_request.get_data()

        if not request_data:
            request_data = b"{}"

        request_data = request_data.decode("utf-8")

        # Get invocation type from headers
        invocation_type = flask_request.headers.get("X-Amz-Invocation-Type", "RequestResponse")

        # Extract tenant-id from request header
        tenant_id = flask_request.headers.get("X-Amz-Tenant-Id")

        # Extract durable execution name from headers
        durable_execution_name = flask_request.headers.get("X-Amz-Durable-Execution-Name")

        stdout_stream_string = io.StringIO()
        stdout_stream_bytes = io.BytesIO()
        stdout_stream_writer = StreamWriter(stdout_stream_string, stdout_stream_bytes, auto_flush=True)

        try:
            # Normalize function name from ARN if provided
            normalized_function_name = normalize_sam_function_identifier(function_name)

            invoke_headers = self.lambda_runner.invoke(
                normalized_function_name,
                request_data,
                invocation_type=invocation_type,
                durable_execution_name=durable_execution_name,
                tenant_id=tenant_id,
                stdout=stdout_stream_writer,
                stderr=self.stderr,
            )
        except (InvalidFunctionNameException, TenantIdValidationError) as e:
            LOG.error("Validation error: %s", str(e))
            return LambdaErrorResponses.validation_exception(str(e))
        except UnsupportedInvocationType as e:
            LOG.warning("invocation-type: %s is not supported. RequestResponse is only supported.", invocation_type)
            return LambdaErrorResponses.not_implemented_locally(str(e))
        except FunctionNotFound:
            LOG.debug("%s was not found to invoke.", normalized_function_name)
            return LambdaErrorResponses.resource_not_found(normalized_function_name)
        except UnsupportedInlineCodeError:
            return LambdaErrorResponses.not_implemented_locally(
                "Inline code is not supported for sam local commands. Please write your code in a separate file."
            )
        except DockerContainerCreationFailedException as ex:
            return LambdaErrorResponses.container_creation_failed(ex.message)

        lambda_response, is_lambda_user_error_response = LambdaOutputParser.get_lambda_output(
            stdout_stream_string, stdout_stream_bytes
        )

        # Prepare headers
        headers = {"Content-Type": "application/json"}
        if invoke_headers and isinstance(invoke_headers, dict):
            headers.update(invoke_headers)

        if is_lambda_user_error_response:
            headers["x-amz-function-error"] = "Unhandled"
            return self.service_response(lambda_response, headers, 200)

        # For async invocations (Event type), return 202
        if invocation_type == "Event":
            return self.service_response("", headers, 202)

        return self.service_response(lambda_response, headers, 200)

    def _get_durable_execution_handler(self, durable_execution_arn):
        """
        Handler for GET /2025-12-01/durable-executions/{DurableExecutionArn}
        """
        # URL-decode the ARN since it comes from the URL path
        decoded_arn = unquote(durable_execution_arn)
        LOG.debug("Calling GetDurableExecution: %s", decoded_arn)

        try:
            with DurableContext() as context:
                response = context.client.get_durable_execution(decoded_arn)
                return self.service_response(
                    json.dumps(response, cls=DateTimeEncoder), {"Content-Type": "application/json"}, 200
                )
        except DurableExecutionNotFound:
            LOG.debug("Durable execution not found: %s", decoded_arn)
            return LambdaErrorResponses.durable_execution_not_found(decoded_arn)

    def _get_durable_execution_history_handler(self, durable_execution_arn):
        """
        Handler for GET /2025-12-01/durable-executions/{DurableExecutionArn}/history
        """
        # URL-decode the ARN since it comes from the URL path
        decoded_arn = unquote(durable_execution_arn)
        LOG.debug("Calling GetDurableExecutionHistory: %s", decoded_arn)

        # Parse query parameters
        include_execution_data = request.args.get("IncludeExecutionData", "false") == "true"

        try:
            with DurableContext() as context:
                response = context.client.get_durable_execution_history(
                    decoded_arn, include_execution_data=include_execution_data
                )
                return self.service_response(
                    json.dumps(response, cls=DateTimeEncoder), {"Content-Type": "application/json"}, 200
                )
        except DurableExecutionNotFound:
            LOG.debug("Durable execution not found: %s", decoded_arn)
            return LambdaErrorResponses.durable_execution_not_found(decoded_arn)

    def _stop_durable_execution_handler(self, durable_execution_arn):
        """
        Handler for POST /2025-12-01/durable-executions/{DurableExecutionArn}/stop
        """
        # URL-decode the ARN since it comes from the URL path
        decoded_arn = unquote(durable_execution_arn)
        LOG.debug("Calling StopDurableExecution: %s", decoded_arn)

        try:
            # Parse request body for error details - handle empty payloads gracefully
            request_data = request.get_json(silent=True) or {}

            with DurableContext() as context:
                response = context.client.stop_durable_execution(
                    durable_execution_arn=decoded_arn,
                    error=request_data.get("Error"),
                )
            return self.service_response(
                json.dumps(response, cls=DateTimeEncoder), {"Content-Type": "application/json"}, 200
            )
        except DurableExecutionNotFound:
            LOG.debug("Durable execution not found: %s", decoded_arn)
            return LambdaErrorResponses.durable_execution_not_found(decoded_arn)
        except Exception as e:
            LOG.error("Failed to stop durable execution: %s", str(e))
            return LambdaErrorResponses.generic_service_exception()

    def _send_callback_success_handler(self, callback_id):
        """
        Handler for POST /2025-12-01/durable-execution-callbacks/{CallbackId}/succeed
        """
        LOG.debug("Calling SendDurableExecutionCallbackSuccess: %s", callback_id)

        try:
            request_data = request.get_json(silent=True) or {}

            with DurableContext() as context:
                response = context.client.send_callback_success(
                    callback_id=callback_id,
                    result=request_data.get("Result"),
                )
            return self.service_response(
                json.dumps(response, cls=DateTimeEncoder), {"Content-Type": "application/json"}, 200
            )
        except Exception as e:
            LOG.error("Failed to send callback success: %s", str(e))
            return LambdaErrorResponses.generic_service_exception()

    def _send_callback_failure_handler(self, callback_id):
        """
        Handler for POST /2025-12-01/durable-execution-callbacks/{CallbackId}/fail
        """
        LOG.debug("Calling SendDurableExecutionCallbackFailure: %s", callback_id)

        try:
            request_data = request.get_json(silent=True) or {}
            with DurableContext() as context:
                response = context.client.send_callback_failure(
                    callback_id=callback_id,
                    error_data=request_data.get("ErrorData"),
                    stack_trace=request_data.get("StackTrace"),
                    error_type=request_data.get("ErrorType"),
                    error_message=request_data.get("ErrorMessage"),
                )
            return self.service_response(
                json.dumps(response, cls=DateTimeEncoder), {"Content-Type": "application/json"}, 200
            )
        except Exception as e:
            LOG.error("Failed to send callback failure: %s", str(e))
            return LambdaErrorResponses.generic_service_exception()

    def _send_callback_heartbeat_handler(self, callback_id):
        """
        Handler for POST /2025-12-01/durable-execution-callbacks/{CallbackId}/heartbeat
        """
        LOG.debug("Calling SendDurableExecutionCallbackHeartbeat: %s", callback_id)

        try:
            with DurableContext() as context:
                response = context.client.send_callback_heartbeat(callback_id=callback_id)
                return self.service_response(
                    json.dumps(response, cls=DateTimeEncoder), {"Content-Type": "application/json"}, 200
                )
        except Exception as e:
            LOG.error("Failed to send callback heartbeat: %s", str(e))
            return LambdaErrorResponses.generic_service_exception()
