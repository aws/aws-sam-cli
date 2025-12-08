"""
Remote invoke executor implementation for Lambda
"""

import base64
import json
import logging
from abc import ABC, abstractmethod
from json import JSONDecodeError
from typing import cast

from botocore.eventstream import EventStream
from botocore.exceptions import ClientError, ParamValidationError
from botocore.response import StreamingBody
from mypy_boto3_lambda.client import LambdaClient

from samcli.lib.remote_invoke.exceptions import (
    ErrorBotoApiCallException,
    InvalideBotoResponseException,
    InvalidResourceBotoParameterException,
)
from samcli.lib.remote_invoke.remote_invoke_executors import (
    BotoActionExecutor,
    RemoteInvokeExecutionInfo,
    RemoteInvokeIterableResponseType,
    RemoteInvokeLogOutput,
    RemoteInvokeOutputFormat,
    RemoteInvokeRequestResponseMapper,
    RemoteInvokeResponse,
)
from samcli.lib.utils import boto_utils

LOG = logging.getLogger(__name__)
FUNCTION_NAME = "FunctionName"
PAYLOAD = "Payload"
TENANT_ID = "TenantId"
DURABLE_EXECUTION_NAME = "DurableExecutionName"
EVENT_STREAM = "EventStream"
PAYLOAD_CHUNK = "PayloadChunk"
INVOKE_COMPLETE = "InvokeComplete"
LOG_RESULT = "LogResult"

INVOKE_MODE = "InvokeMode"
RESPONSE_STREAM = "RESPONSE_STREAM"


class AbstractLambdaInvokeExecutor(BotoActionExecutor, ABC):
    """
    Abstract class for different lambda invocation executors, see implementation for details.
    For Payload parameter, if a file location provided, the file handle will be passed as Payload object
    """

    _lambda_client: LambdaClient
    _function_name: str
    _remote_output_format: RemoteInvokeOutputFormat

    def __init__(self, lambda_client: LambdaClient, function_name: str, remote_output_format: RemoteInvokeOutputFormat):
        self._lambda_client = lambda_client
        self._function_name = function_name
        self._remote_output_format = remote_output_format
        self.request_parameters = {"InvocationType": "RequestResponse", "LogType": "Tail"}

    def execute(self, remote_invoke_input: RemoteInvokeExecutionInfo) -> RemoteInvokeIterableResponseType:
        """
        Override execute to extract tenant_id from RemoteInvokeExecutionInfo for Lambda-specific handling.
        """
        if remote_invoke_input.tenant_id:
            self.request_parameters[TENANT_ID] = remote_invoke_input.tenant_id

        if remote_invoke_input.durable_execution_name:
            self.request_parameters[DURABLE_EXECUTION_NAME] = remote_invoke_input.durable_execution_name

        return super().execute(remote_invoke_input)

    def validate_action_parameters(self, parameters: dict) -> None:
        """
        Validates the input boto parameters and prepares the parameters for calling the API.

        Parameters
        ----------
        parameters: dict
            Boto parameters provided as input
        """
        for parameter_key, parameter_value in parameters.items():
            if parameter_key == FUNCTION_NAME:
                LOG.warning("FunctionName is defined using the value provided for resource_id argument.")
            elif parameter_key == PAYLOAD:
                LOG.warning("Payload is defined using the value provided for either --event or --event-file options.")
            else:
                self.request_parameters[parameter_key] = parameter_value

    def _execute_action(self, payload: str) -> RemoteInvokeIterableResponseType:
        self.request_parameters[FUNCTION_NAME] = self._function_name
        self.request_parameters[PAYLOAD] = payload

        return self._execute_lambda_invoke(payload)

    def _execute_boto_call(self, boto_client_method) -> dict:
        try:
            return cast(dict, boto_client_method(**self.request_parameters))
        except ParamValidationError as param_val_ex:
            raise InvalidResourceBotoParameterException(
                f"Invalid parameter key provided."
                f" {str(param_val_ex).replace(f'{FUNCTION_NAME}, ', '').replace(f'{PAYLOAD}, ', '')}"
            ) from param_val_ex
        except ClientError as client_ex:
            error_code = boto_utils.get_client_error_code(client_ex)
            error_message = str(client_ex)

            # Check if this is a capacity provider error about tail logs
            if (
                error_code == "InvalidParameterValueException"
                and "Tail logs are not supported for functions" in error_message
            ):
                # Remove LogType and retry
                self.request_parameters.pop("LogType", None)
                try:
                    return cast(dict, boto_client_method(**self.request_parameters))
                except ClientError as retry_ex:
                    error_code = boto_utils.get_client_error_code(retry_ex)
                    error_message = str(retry_ex)

            if error_code == "ValidationException":
                raise InvalidResourceBotoParameterException(
                    f"Invalid parameter value provided. {str(client_ex).replace('(ValidationException) ', '')}"
                ) from client_ex
            elif error_code == "InvalidRequestContentException":
                raise InvalidResourceBotoParameterException(client_ex) from client_ex
            raise ErrorBotoApiCallException(client_ex) from client_ex

    def _process_log_result(self, log_result: str) -> RemoteInvokeLogOutput:
        """
        Process the log result from Lambda invocation.

        The log_result can be in one of two formats:
        1. Traditional format: Base64-encoded string containing the last 4KB of function logs
        2. New format: Base64-encoded JSON containing logGroup and logStreamName references

        Parameters
        ----------
        log_result : str
            Base64-encoded log result from Lambda invocation

        Returns
        -------
        RemoteInvokeLogOutput
            Log output object containing either the decoded logs or a message with log reference
        """
        decoded_log = base64.b64decode(log_result).decode("utf-8")

        # Try to parse as JSON to check if it's the new format
        try:
            log_data = json.loads(decoded_log)

            # Check if it has the expected fields for the new format
            if isinstance(log_data, dict) and "logGroup" in log_data and "logStreamName" in log_data:
                log_group = log_data.get("logGroup")
                log_stream = log_data.get("logStreamName")

                LOG.debug("Detected new log result format with CloudWatch references")

                # Create a helpful message for the user
                message = (
                    f"Function logs are available in CloudWatch Logs:\n"
                    f"Log Group: {log_group}\n"
                    f"Log Stream: {log_stream}\n\n"
                )

                return RemoteInvokeLogOutput(message)
        except JSONDecodeError:
            # Not JSON, treat as regular log content
            LOG.debug("Log result is in traditional format (raw logs)")
            pass

        # Default case: return the decoded log as is
        return RemoteInvokeLogOutput(decoded_log)

    @abstractmethod
    def _execute_lambda_invoke(self, payload: str) -> RemoteInvokeIterableResponseType:
        raise NotImplementedError()


class LambdaInvokeExecutor(AbstractLambdaInvokeExecutor):
    """
    Calls "invoke" method of "lambda" service with given input.
    """

    def _execute_lambda_invoke(self, payload: str) -> RemoteInvokeIterableResponseType:
        LOG.debug(
            "Calling lambda_client.invoke with FunctionName:%s, Payload:%s, parameters:%s",
            self._function_name,
            payload,
            self.request_parameters,
        )
        lambda_response = self._execute_boto_call(self._lambda_client.invoke)
        if self._remote_output_format == RemoteInvokeOutputFormat.JSON:
            yield RemoteInvokeResponse(lambda_response)
        if self._remote_output_format == RemoteInvokeOutputFormat.TEXT:
            log_result = lambda_response.get(LOG_RESULT)
            if log_result:
                yield self._process_log_result(log_result)
            yield RemoteInvokeResponse(cast(StreamingBody, lambda_response.get(PAYLOAD)).read().decode("utf-8"))


class LambdaInvokeWithResponseStreamExecutor(AbstractLambdaInvokeExecutor):
    """
    Calls "invoke_with_response_stream" method of "lambda" service with given input.
    """

    def _execute_lambda_invoke(self, payload: str) -> RemoteInvokeIterableResponseType:
        LOG.debug(
            "Calling lambda_client.invoke_with_response_stream with FunctionName:%s, Payload:%s, parameters:%s",
            self._function_name,
            payload,
            self.request_parameters,
        )
        lambda_response = self._execute_boto_call(self._lambda_client.invoke_with_response_stream)
        if self._remote_output_format == RemoteInvokeOutputFormat.JSON:
            yield RemoteInvokeResponse(lambda_response)
        if self._remote_output_format == RemoteInvokeOutputFormat.TEXT:
            event_stream: EventStream = lambda_response.get(EVENT_STREAM, [])
            for event in event_stream:
                if PAYLOAD_CHUNK in event:
                    yield RemoteInvokeResponse(event.get(PAYLOAD_CHUNK).get(PAYLOAD).decode("utf-8"))
                if INVOKE_COMPLETE in event:
                    if LOG_RESULT in event.get(INVOKE_COMPLETE):
                        yield self._process_log_result(event.get(INVOKE_COMPLETE).get(LOG_RESULT))


class DefaultConvertToJSON(RemoteInvokeRequestResponseMapper[RemoteInvokeExecutionInfo]):
    """
    If a regular string is provided as payload, this class will convert it into a JSON object
    """

    def map(self, test_input: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        if not test_input.is_file_provided():
            if not test_input.payload:
                LOG.debug("Input event not found, invoking resource with an empty event")
                test_input.payload = "{}"
            LOG.debug("Mapping input event to JSON string object")
            try:
                _ = json.loads(cast(str, test_input.payload))
            except JSONDecodeError:
                json_value = json.dumps(test_input.payload)
                LOG.info(
                    "Auto converting value '%s' into JSON '%s'. "
                    "If you don't want auto-conversion, please provide a JSON string as event",
                    test_input.payload,
                    json_value,
                )
                test_input.payload = json_value

        return test_input


class LambdaResponseConverter(RemoteInvokeRequestResponseMapper[RemoteInvokeResponse]):
    """
    This class helps to convert response from lambda service. Normally lambda service
    returns 'Payload' field as stream, this class converts that stream into string object
    """

    def map(self, remote_invoke_input: RemoteInvokeResponse) -> RemoteInvokeResponse:
        LOG.debug("Mapping Lambda response to string object")
        if not isinstance(remote_invoke_input.response, dict):
            raise InvalideBotoResponseException("Invalid response type received from Lambda service, expecting dict")

        payload_field = remote_invoke_input.response.get(PAYLOAD)
        if payload_field:
            remote_invoke_input.response[PAYLOAD] = cast(StreamingBody, payload_field).read().decode("utf-8")

        return remote_invoke_input


class LambdaStreamResponseConverter(RemoteInvokeRequestResponseMapper):
    """
    This class helps to convert response from lambda invoke_with_response_stream API call.
    That API call returns 'EventStream' which yields 'PayloadChunk's and 'InvokeComplete' as they become available.
    This mapper, gets all 'PayloadChunk's and 'InvokeComplete' events and decodes them for next mapper.
    """

    def map(self, remote_invoke_input: RemoteInvokeResponse) -> RemoteInvokeResponse:
        LOG.debug("Mapping Lambda response to string object")
        if not isinstance(remote_invoke_input.response, dict):
            raise InvalideBotoResponseException("Invalid response type received from Lambda service, expecting dict")

        event_stream: EventStream = remote_invoke_input.response.get(EVENT_STREAM, [])
        decoded_event_stream = []
        for event in event_stream:
            if PAYLOAD_CHUNK in event:
                decoded_payload_chunk = event.get(PAYLOAD_CHUNK).get(PAYLOAD).decode("utf-8")
                decoded_event_stream.append({PAYLOAD_CHUNK: {PAYLOAD: decoded_payload_chunk}})
            if INVOKE_COMPLETE in event:
                decoded_event_stream.append(event)
        remote_invoke_input.response[EVENT_STREAM] = decoded_event_stream
        return remote_invoke_input


class DurableFunctionQualifierMapper(RemoteInvokeRequestResponseMapper[RemoteInvokeExecutionInfo]):
    """
    Sets Qualifier to $LATEST for durable functions if not already specified
    """

    def map(self, test_input: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        test_input.parameters.setdefault("Qualifier", "$LATEST")
        return test_input


def _is_function_invoke_mode_response_stream(lambda_client: LambdaClient, function_name: str):
    """
    Returns True if given function has RESPONSE_STREAM as InvokeMode, False otherwise
    """
    try:
        function_url_config = lambda_client.get_function_url_config(FunctionName=function_name)
        function_invoke_mode = function_url_config.get(INVOKE_MODE)
        LOG.debug("InvokeMode of function %s: %s", function_name, function_invoke_mode)
        return function_invoke_mode == RESPONSE_STREAM
    except ClientError as ex:
        LOG.debug("Function %s, doesn't have Function URL configured, using regular invoke", function_name, exc_info=ex)
        return False


def _is_durable_function(lambda_client: LambdaClient, function_name: str) -> bool:
    """
    Returns True if given function is a durable function, False otherwise
    """
    try:
        response = lambda_client.get_function_configuration(FunctionName=function_name)
        LOG.debug("Function configuration for %s: %s", function_name, response)
        is_durable = response.get("DurableConfig") is not None
        LOG.debug("Function %s is durable: %s", function_name, is_durable)
        return is_durable
    except Exception as ex:
        LOG.info("Failed to get function configuration for %s: %s", function_name, ex)
        # If we can't determine, assume it's not a durable function
        return False
