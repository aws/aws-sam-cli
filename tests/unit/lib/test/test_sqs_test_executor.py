from json import JSONDecodeError
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.test.sqs_test_executor import SqsSendMessageExecutor, SqsConvertToEntriesJsonObject
from samcli.lib.test.test_executors import TestExecutionInfo


class TestSqsSendMessageExecutor(TestCase):
    def setUp(self) -> None:
        self.sqs_client = Mock()
        self.sqs_queue_url = Mock()
        self.sqs_send_message_executor = SqsSendMessageExecutor(self.sqs_client, self.sqs_queue_url)

    def test_execute_action(self):
        given_payload = Mock()
        given_result = Mock()
        self.sqs_client.send_message_batch.return_value = given_result

        result = self.sqs_send_message_executor._execute_action(given_payload)

        self.assertEqual(result, given_result)
        self.sqs_client.send_message_batch.assert_called_with(QueueUrl=self.sqs_queue_url, Entries=given_payload)

    @patch("samcli.lib.test.sqs_test_executor.json")
    def test_execute_action_file(self, patched_json):
        given_result = Mock()
        self.sqs_client.send_message_batch.return_value = given_result

        given_file_contents = Mock()
        given_payload_file = Mock()
        given_payload_file.read.return_value = given_file_contents

        given_json_object = Mock()
        patched_json.loads.return_value = given_json_object

        result = self.sqs_send_message_executor._execute_action_file(given_payload_file)

        self.assertEqual(result, given_result)
        given_payload_file.read.assert_called_once()
        patched_json.loads.assert_called_with(given_file_contents)
        self.sqs_client.send_message_batch.assert_called_with(QueueUrl=self.sqs_queue_url, Entries=given_json_object)

    @patch("samcli.lib.test.sqs_test_executor.json")
    def test_execute_action_file_exception(self, patched_json):
        given_payload_file = Mock()

        patched_json.loads.side_effect = JSONDecodeError("msg", "doc", 1)

        with self.assertRaises(JSONDecodeError):
            self.sqs_send_message_executor._execute_action_file(given_payload_file)


class TestSqsConvertToEntriesJsonObject(TestCase):
    def setUp(self) -> None:
        self.sqs_convert_to_json_object = SqsConvertToEntriesJsonObject()

    def test_conversion(self):
        given_content = "Hello World"
        test_execution_info = TestExecutionInfo(given_content, None)

        result = self.sqs_convert_to_json_object.map(test_execution_info)

        self.assertEqual(given_content, result.payload[0]["MessageBody"])
        self.assertTrue("Id" in result.payload[0])
