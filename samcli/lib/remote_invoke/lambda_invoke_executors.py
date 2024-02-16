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
            if boto_utils.get_client_error_code(client_ex) == "ValidationException":
                raise InvalidResourceBotoParameterException(
                    f"Invalid parameter value provided. {str(client_ex).replace('(ValidationException) ', '')}"
                ) from client_ex
            elif boto_utils.get_client_error_code(client_ex) == "InvalidRequestContentException":
                raise InvalidResourceBotoParameterException(client_ex) from client_ex
            raise ErrorBotoApiCallException(client_ex) from client_ex

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
                yield RemoteInvokeLogOutput(base64.b64decode(log_result).decode("utf-8"))
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
                        yield RemoteInvokeLogOutput(
                            base64.b64decode(event.get(INVOKE_COMPLETE).get(LOG_RESULT)).decode("utf-8")
                        )


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
