"""
Remote invoke executor implementation for Lambda
"""
import base64
import json
import logging
from json import JSONDecodeError
from typing import Any, Dict, cast

from botocore.response import StreamingBody

from samcli.lib.remote_invoke.exceptions import InvalidResourceBotoParameterException
from samcli.lib.remote_invoke.remote_invoke_executors import (
    BotoActionExecutor,
    RemoteInvokeExecutionInfo,
    RemoteInvokeRequestResponseMapper,
)

LOG = logging.getLogger(__name__)


class LambdaInvokeExecutor(BotoActionExecutor):
    """
    Calls "invoke" method of "lambda" service with given input.
    If a file location provided, the file handle will be passed as Payload object
    """

    _lambda_client: Any
    _function_name: str
    _SUPPORTED_PARAMETERS: dict = {
        "InvocationType": ["Event", "RequestResponse", "DryRun"],
        "LogType": ["None", "Tail"],
        "Qualifier": [],
    }

    def __init__(self, lambda_client: Any, function_name: str):
        self._lambda_client = lambda_client
        self._function_name = function_name
        self.request_parameters = {"InvocationType": "RequestResponse", "LogType": "Tail"}

    def validate_action_parameters(self, parameters: dict):
        """
        Validates the input boto parameters and prepares the parameters for calling the API.

        :param parameters: Boto parameters provided as input
        """
        for parameter_key, parameter_value in parameters.items():
            parameter_allowed_values = self._SUPPORTED_PARAMETERS.get(parameter_key, [])
            if parameter_key == "FunctionName":
                LOG.info("FunctionName is defined using the value provided for --resource-id option.")
            elif parameter_key == "Payload":
                LOG.info("Payload is defined using the value provided for either --payload or --payload-file options.")
            elif parameter_key not in self._SUPPORTED_PARAMETERS:
                error_msg = (
                    f"Provided parameter is not supported for invoking the resource {self._function_name}."
                    f" Please provide a valid parameter from this list: {list(self._SUPPORTED_PARAMETERS.keys())}"
                )
                raise InvalidResourceBotoParameterException(error_msg)
            elif parameter_allowed_values and parameter_value not in parameter_allowed_values:
                error_msg = (
                    f"Invalid value provided for the parameter {parameter_key}."
                    f" Please provide a value from this list: {parameter_allowed_values}"
                )
                raise InvalidResourceBotoParameterException(error_msg)
            else:
                self.request_parameters[parameter_key] = parameter_value

    def _execute_action(self, payload: str):
        self.request_parameters["FunctionName"] = self._function_name
        self.request_parameters["Payload"] = payload
        LOG.debug(
            "Calling lambda_client.invoke with FunctionName:%s, Payload:%s, parameters:%s",
            self._function_name,
            payload,
            self.request_parameters,
        )
        return self._lambda_client.invoke(**self.request_parameters)


class DefaultConvertToJSON(RemoteInvokeRequestResponseMapper):
    """
    If a regular string is provided as payload, this class will convert it into a JSON object
    """

    def map(self, test_input: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        if not test_input.is_file_provided():
            try:
                _ = json.loads(cast(str, test_input.payload))
            except JSONDecodeError:
                json_value = json.dumps(test_input.payload)
                LOG.info(
                    "Auto converting value '%s' into JSON '%s'. "
                    "If you don't want auto-conversion, please provide a JSON string as payload",
                    test_input.payload,
                    json_value,
                )
                test_input.payload = json_value

        return test_input


class LambdaResponseConverter(RemoteInvokeRequestResponseMapper):
    """
    This class helps to convert response from lambda service. Normally lambda service
    returns 'Payload' field as stream, this class converts that stream into string object
    """

    def map(self, remote_invoke_input: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        assert isinstance(remote_invoke_input.response, dict), "Invalid response type received, expecting dict"
        payload_field = remote_invoke_input.response.get("Payload")
        if payload_field:
            remote_invoke_input.response["Payload"] = cast(StreamingBody, payload_field).read().decode("utf-8")

        return remote_invoke_input


class LambdaResponseOutputFormatter(RemoteInvokeRequestResponseMapper):
    """
    This class helps to format output response for lambda service that will be printed on the CLI.
    If LogResult is found in the response, the decoded LogResult will be written to stderr. The response payload will
    be written to stdout.
    """

    def map(self, remote_invoke_input: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        """
        Maps the lambda response output to the type of output format specified by customer.
        If output_format is original-boto-response, write the original boto repsonse
        to stdout.
        """
        if remote_invoke_input.output_format == "default":
            boto_response = cast(Dict, remote_invoke_input.response)
            log_field = boto_response.get("LogResult")
            if log_field:
                log_result = base64.b64decode(log_field).decode("utf-8")
                remote_invoke_input.stderr_str = log_result

            invocation_type_parameter = remote_invoke_input.parameters.get("InvocationType")
            if invocation_type_parameter and invocation_type_parameter != "RequestResponse":
                remote_invoke_input.response = {"StatusCode": boto_response["StatusCode"]}
            else:
                remote_invoke_input.response = boto_response.get("Payload")

        return remote_invoke_input
