"""
Test executor implementation for Kinesis
"""
import json
import logging
import uuid
import base64
from io import TextIOWrapper
from json import JSONDecodeError
from typing import Any

from samcli.lib.test.test_executors import BotoActionExecutor, TestRequestResponseMapper, TestExecutionInfo

LOG = logging.getLogger(__name__)


class KinesisPutRecordsExecutor(BotoActionExecutor):
    """
    Calls "put_records" method of "kinesis" service with given input.
    If a file location provided, the file contents will be read and parse as JSON.
    """

    _kinesis_client: Any
    _stream_name: str

    def __init__(self, kinesis_client: Any, stream_name: str):
        self._kinesis_client = kinesis_client
        self._stream_name = stream_name

    def _execute_action(self, payload: str):
        LOG.debug("Calling kinesis_client.put_records with StreamName:%s, Records:%s", self._stream_name, payload)
        return self._kinesis_client.put_records(StreamName=self._stream_name, Records=payload)

    def _execute_action_file(self, payload_file: TextIOWrapper):
        try:
            entries = json.loads(payload_file.read())
        except JSONDecodeError as e:
            LOG.error("Invalid file (%s) contents. File should contain valid JSON", str(payload_file))
            raise e

        LOG.debug("Calling kinesis_client.put_records with StreamName:%s, Records:%s", self._stream_name, entries)
        return self._kinesis_client.put_records(StreamName=self._stream_name, Records=entries)


class KinesisConvertToRecordsJsonObject(TestRequestResponseMapper):
    """
    Creates 'Records' parameter from given string by converting it to a JSON object
    and adding auto generated 'PartitionKey'.
    """

    def map(self, test_input: TestExecutionInfo) -> TestExecutionInfo:
        if not test_input.is_file_provided():
            data = base64.b64encode(str(test_input.payload).encode())
            json_value = f'[{{ "Data": "{str(data)}", "PartitionKey": "{str(uuid.uuid4())}"  }}]'
            LOG.info("Auto converting value '%s' into JSON '%s'. ", test_input.payload, json_value)
            test_input.payload = json.loads(json_value)

        return test_input
