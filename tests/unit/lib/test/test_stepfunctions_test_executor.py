import base64

from json import JSONDecodeError
from typing import Any
from unittest import TestCase
from unittest.mock import ANY, Mock, patch

from samcli.lib.test.stepfunctions_test_executor import StepFunctionsStartExecutionExecutor


class TestStepFunctionsStartExecutionExecutor(TestCase):
    def setUp(self) -> None:
        self.stepfunctions_client = Mock()
        self.statemachine_arn = Mock()
        self.stepfunctions_start_execution_executor = StepFunctionsStartExecutionExecutor(
            self.stepfunctions_client, self.statemachine_arn
        )

    def test_execute_action(self):
        given_payload = Mock()
        given_result = Mock()
        self.stepfunctions_client.start_execution.return_value = given_result

        result = self.stepfunctions_start_execution_executor._execute_action(given_payload)

        self.assertEqual(result, given_result)
        self.stepfunctions_client.start_execution.assert_called_with(
            name=ANY, input=given_payload, stateMachineArn=self.statemachine_arn
        )
