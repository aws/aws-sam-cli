"""
Test executor implementation for Lambda
"""
import json
import logging
from json import JSONDecodeError
from typing import Any, cast

from botocore.response import StreamingBody

from samcli.lib.test.test_executors import BotoActionExecutor, TestRequestResponseMapper, TestExecutionInfo

LOG = logging.getLogger(__name__)


class LambdaInvokeExecutor(BotoActionExecutor):
    """
    Calls "invoke" method of "lambda" service with given input.
    If a file location provided, the file handle will be passed as Payload object
    """

    _lambda_client: Any
    _function_name: str

    def __init__(self, lambda_client: Any, function_name: str):
        self._lambda_client = lambda_client
        self._function_name = function_name

    def _execute_action(self, payload: str):
        LOG.debug("Calling lambda_client.invoke with FunctionName:%s, Payload:%s", self._function_name, payload)
        return self._lambda_client.invoke(FunctionName=self._function_name, Payload=payload)


class DefaultConvertToJSON(TestRequestResponseMapper):
    """
    If a regular string is provided as payload, this class will convert it into a JSON object
    """

    def map(self, test_input: TestExecutionInfo) -> TestExecutionInfo:
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


class LambdaResponseConverter(TestRequestResponseMapper):
    """
    This class helps to convert response from lambda service. Normally lambda service
    returns 'Payload' field as stream, this class converts that stream into string object
    """

    def map(self, test_input: TestExecutionInfo) -> TestExecutionInfo:
        assert isinstance(test_input.response, dict), "Invalid response type received, expecting dict"
        payload_field = test_input.response.get("Payload")
        if payload_field:
            test_input.response["Payload"] = cast(StreamingBody, payload_field).read().decode("utf-8")

        return test_input
