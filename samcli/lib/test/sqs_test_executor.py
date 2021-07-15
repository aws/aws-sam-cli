"""
Test executor implementation for SQS
"""
import json
import logging
import uuid
from io import TextIOWrapper
from json import JSONDecodeError
from typing import Any

from samcli.lib.test.test_executors import BotoActionExecutor, TestRequestResponseMapper, TestExecutionInfo

LOG = logging.getLogger(__name__)


class SqsSendMessageExecutor(BotoActionExecutor):
    """
    Calls "send_message_batch" method of "sqs" service with given input.
    If a file location provided, the file contents will be read and parse as JSON.
    """

    _sqs_client: Any
    _sqs_queue_url: str

    def __init__(self, sqs_client: Any, sqs_queue_url: str):
        self._sqs_client = sqs_client
        self._sqs_queue_url = sqs_queue_url

    def _execute_action(self, payload: str):
        LOG.debug("Calling sqs_client.send_message_batch with QueueUrl:%s, Entries:%s", self._sqs_queue_url, payload)
        return self._sqs_client.send_message_batch(QueueUrl=self._sqs_queue_url, Entries=payload)

    def _execute_action_file(self, payload_file: TextIOWrapper):
        try:
            entries = json.loads(payload_file.read())
        except JSONDecodeError as e:
            LOG.error("Invalid file (%s) contents. File should contain valid JSON", str(payload_file))
            raise e

        LOG.debug("Calling sqs_client.send_message_batch with QueueUrl:%s, Entries:%s", self._sqs_queue_url, entries)
        return self._sqs_client.send_message_batch(QueueUrl=self._sqs_queue_url, Entries=entries)


class SqsConvertToEntriesJsonObject(TestRequestResponseMapper):
    """
    Creates 'Entries' parameter from given string by converting it to a JSON object and adding auto generated 'Id' field
    """

    def map(self, test_input: TestExecutionInfo) -> TestExecutionInfo:
        if not test_input.is_file_provided():
            json_value = f'[{{ "MessageBody": "{test_input.payload}", "Id": "{str(uuid.uuid4())}"  }}]'
            LOG.info("Auto converting value '%s' into JSON '%s'. ", test_input.payload, json_value)
            test_input.payload = json.loads(json_value)

        return test_input
