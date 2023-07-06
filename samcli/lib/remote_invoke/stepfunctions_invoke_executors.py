import logging
import time
from typing import Any

from botocore.exceptions import ClientError, ParamValidationError

from samcli.lib.remote_invoke.exceptions import (
    ErrorBotoApiCallException,
    InvalideBotoResponseException,
    InvalidResourceBotoParameterException,
)
from samcli.lib.remote_invoke.remote_invoke_executors import (
    BotoActionExecutor,
    RemoteInvokeLogOutput,
    RemoteInvokeOutputFormat,
    RemoteInvokeRequestResponseMapper,
    RemoteInvokeResponse,
)

LOG = logging.getLogger(__name__)
STATE_MACHINE_ARN = "stateMachineArn"
EXECUTION_ARN = "executionArn"
INPUT = "input"
RUNNING = "RUNNING"
SFN_EXECUTION_WAIT_TIME = 2


class StepFunctionsStartExecutionExecutor(BotoActionExecutor):
    """
    Calls "start_execution" method of "stepfunctions" service with given input.
    If a file location provided, the file handle will be passed as Payload object
    """

    _stepfunctions_client: Any
    _state_machine_arn: str
    _remote_output_format: RemoteInvokeOutputFormat
    request_parameters: dict

    def __init__(self, stepfunctions_client: Any, physical_id: str, remote_output_format: RemoteInvokeOutputFormat):
        self._stepfunctions_client = stepfunctions_client
        self._remote_output_format = remote_output_format
        self._state_machine_arn = physical_id
        self.request_parameters = {}

    def validate_action_parameters(self, parameters: dict):
        for parameter_key, parameter_value in parameters.items():
            if parameter_key == "stateMachineArn":
                LOG.warning("stateMachineArn is defined using the value provided for resource_id argument.")
            elif parameter_key == "input":
                LOG.warning("input is defined using the value provided for either --event or --event-file options.")
            else:
                self.request_parameters[parameter_key] = parameter_value

        if not self.request_parameters.get("name"):
            timestamp = str(int(time.time() * 1000))
            self.request_parameters["name"] = f"sam_remote_invoke_{timestamp}"

    def _execute_action(self, payload: str):
        self.request_parameters[INPUT] = payload
        self.request_parameters[STATE_MACHINE_ARN] = self._state_machine_arn
        LOG.debug(
            "Calling stepfunctions_client.start_execution with name:%s, input:%s, stateMachineArn:%s",
            self.request_parameters["name"],
            payload,
            self._state_machine_arn,
        )
        try:
            start_execution_response = self._stepfunctions_client.start_execution(**self.request_parameters)
            execution_arn = start_execution_response.get(EXECUTION_ARN)

            describe_execution_response = self._stepfunctions_client.describe_execution(executionArn=execution_arn)
            while describe_execution_response["status"] == RUNNING:
                describe_execution_response = self._stepfunctions_client.describe_execution(executionArn=execution_arn)
                time.sleep(SFN_EXECUTION_WAIT_TIME)

            if self._remote_output_format == RemoteInvokeOutputFormat.JSON:
                yield RemoteInvokeResponse(describe_execution_response)
            if self._remote_output_format == RemoteInvokeOutputFormat.TEXT:
                output_data = describe_execution_response.get("output", "")
                error_data = describe_execution_response.get("error", "")
                yield RemoteInvokeResponse(output_data)
                if error_data:
                    error_cause = describe_execution_response.get("cause", "")
                    yield RemoteInvokeLogOutput(
                        f"The execution failed due to the error: {error_data} and cause: {error_cause}"
                    )
        except ParamValidationError as param_val_ex:
            raise InvalidResourceBotoParameterException(
                f"Invalid parameter key provided."
                f" {str(param_val_ex).replace(f'{STATE_MACHINE_ARN}, ', '').replace(f'{INPUT}, ', '')}"
            )
        except ClientError as client_ex:
            raise ErrorBotoApiCallException(client_ex) from client_ex


class SfnDescribeExecutionResponseConverter(RemoteInvokeRequestResponseMapper[RemoteInvokeResponse]):
    """
    This class helps to convert response from Step Function service.
    This class converts any datetime objects in the response into strings
    """

    def map(self, remote_invoke_input: RemoteInvokeResponse) -> RemoteInvokeResponse:
        LOG.debug("Mapping Step Function execution response to string object")
        if not isinstance(remote_invoke_input.response, dict):
            raise InvalideBotoResponseException(
                "Invalid response type received from Step Functions service, expecting dict"
            )

        start_date_field = remote_invoke_input.response.get("startDate")
        stop_date_field = remote_invoke_input.response.get("stopDate")
        if start_date_field:
            remote_invoke_input.response["startDate"] = start_date_field.strftime("%m/%d/%Y")
        if stop_date_field:
            remote_invoke_input.response["stopDate"] = stop_date_field.strftime("%m/%d/%Y")
        return remote_invoke_input
