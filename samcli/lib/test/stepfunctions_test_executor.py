"""
Test executor implementation for StepFunctions
"""
import logging
import time
from typing import Any

from samcli.lib.test.test_executors import BotoActionExecutor

LOG = logging.getLogger(__name__)


class StepFunctionsStartExecutionExecutor(BotoActionExecutor):
    """
    Calls "start_execution" method of "stepfunctions" service with given input.
    If a file location provided, the file handle will be passed as Payload object
    """

    _stepfunctions_client: Any
    _physical_id: str
    _state_machine_arn: str

    def __init__(self, stepfunctions_client: Any, physical_id: str):
        self._stepfunctions_client = stepfunctions_client
        self._state_machine_arn = physical_id

    def _execute_action(self, payload: str):
        timestamp = str(int(time.time() * 1000))
        name = f"sam_test_{timestamp}"
        LOG.debug(
            "Calling stepfunctions_client.start_execution with name:%s, input:%s, stateMachineArn:%s",
            name,
            payload,
            self._state_machine_arn,
        )
        return self._stepfunctions_client.start_execution(
            name=name, input=payload, stateMachineArn=self._state_machine_arn
        )
