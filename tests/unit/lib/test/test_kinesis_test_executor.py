import base64

from json import JSONDecodeError
from typing import Any
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.test.kinesis_test_executor import KinesisPutRecordsExecutor, KinesisConvertToRecordsJsonObject
from samcli.lib.test.test_executors import TestExecutionInfo


class TestKinesisPutRecordsExecutor(TestCase):
    def setUp(self) -> None:
        self.kinesis_client = Mock()
        self.stream_name = Mock()
        self.kinesis_put_records_executor = KinesisPutRecordsExecutor(self.kinesis_client, self.stream_name)

    def test_execute_action(self):
        given_payload = Mock()
        given_result = Mock()
        self.kinesis_client.put_records.return_value = given_result

        result = self.kinesis_put_records_executor._execute_action(given_payload)

        self.assertEqual(result, given_result)
        self.kinesis_client.put_records.assert_called_with(StreamName=self.stream_name, Records=given_payload)

    @patch("samcli.lib.test.kinesis_test_executor.json")
    def test_execute_action_file(self, patched_json):
        given_result = Mock()
        self.kinesis_client.put_records.return_value = given_result

        given_file_contents = Mock()
        given_payload_file = Mock()
        given_payload_file.read.return_value = given_file_contents

        given_json_object = Mock()
        patched_json.loads.return_value = given_json_object

        result = self.kinesis_put_records_executor._execute_action_file(given_payload_file)

        self.assertEqual(result, given_result)
        given_payload_file.read.assert_called_once()
        patched_json.loads.assert_called_with(given_file_contents)
        self.kinesis_client.put_records.assert_called_with(StreamName=self.stream_name, Records=given_json_object)

    @patch("samcli.lib.test.kinesis_test_executor.json")
    def test_execute_action_file_exception(self, patched_json):
        given_payload_file = Mock()

        patched_json.loads.side_effect = JSONDecodeError("msg", "doc", 1)

        with self.assertRaises(JSONDecodeError):
            self.kinesis_put_records_executor._execute_action_file(given_payload_file)


class TestKinesisConvertToRecordsJsonObject(TestCase):
    def setUp(self) -> None:
        self.kinesis_convert_to_json_object = KinesisConvertToRecordsJsonObject()

    def test_conversion(self):
        given_content = "Hello World"
        test_execution_info = TestExecutionInfo(given_content, None)

        result = self.kinesis_convert_to_json_object.map(test_execution_info)

        self.assertEqual(f"{str(base64.b64encode(given_content.encode()))}", result.payload[0]["Data"])
        self.assertTrue("PartitionKey" in result.payload[0])
