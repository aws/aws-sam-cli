from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized, parameterized_class
from samcli.lib.remote_invoke.kinesis_invoke_executors import (
    RemoteInvokeOutputFormat,
    KinesisPutDataExecutor,
    ParamValidationError,
    InvalidResourceBotoParameterException,
    ErrorBotoApiCallException,
    ClientError,
    KinesisStreamPutRecordTextOutput,
)
from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeResponse


class TestKinesisStreamPutRecordTextOutput(TestCase):
    @parameterized.expand(
        [
            ("mock-shard-id", "mock-sequence-number"),
        ]
    )
    def test_kinesis_put_record_text_output(self, shard_id, sequence_number):
        text_output = KinesisStreamPutRecordTextOutput(ShardId=shard_id, SequenceNumber=sequence_number)
        self.assertEqual(text_output.ShardId, shard_id)
        self.assertEqual(text_output.SequenceNumber, sequence_number)

    @parameterized.expand(
        [
            (
                "mock-shard-id",
                "mock-sequence-number",
                {
                    "ShardId": "mock-shard-id",
                    "SequenceNumber": "mock-sequence-number",
                },
            ),
        ]
    )
    def test_get_output_response_dict(self, shard_id, sequence_number, expected_output):
        text_output = KinesisStreamPutRecordTextOutput(ShardId=shard_id, SequenceNumber=sequence_number)
        output_response_dict = text_output.get_output_response_dict()
        self.assertEqual(output_response_dict, expected_output)


@parameterized_class(
    "output",
    [[RemoteInvokeOutputFormat.TEXT], [RemoteInvokeOutputFormat.JSON]],
)
class TestKinesisPutDataExecutor(TestCase):
    output: RemoteInvokeOutputFormat

    def setUp(self) -> None:
        self.kinesis_client = Mock()
        self.stream_name = "mock-kinesis-stream"
        self.kinesis_put_data_executor = KinesisPutDataExecutor(self.kinesis_client, self.stream_name, self.output)

    @patch("samcli.lib.remote_invoke.kinesis_invoke_executors.uuid")
    def test_execute_action_successful(self, patched_uuid):
        mock_uuid_value = "patched-uuid-value"
        patched_uuid.uuid4.return_value = mock_uuid_value
        given_input_data = "hello world"
        mock_shard_id = "shardId-000000000000"
        mock_sequence_number = "2941492a-5847-4ebb-a8a3-58c07ce9f198"
        mock_text_response = {
            "ShardId": mock_shard_id,
            "SequenceNumber": mock_sequence_number,
        }

        mock_json_response = {
            "ShardId": mock_shard_id,
            "SequenceNumber": mock_sequence_number,
            "ResponseMetadata": {},
        }
        self.kinesis_client.put_record.return_value = {
            "ShardId": mock_shard_id,
            "SequenceNumber": mock_sequence_number,
            "ResponseMetadata": {},
        }
        self.kinesis_put_data_executor.validate_action_parameters({})
        result = self.kinesis_put_data_executor._execute_action(given_input_data)
        if self.output == RemoteInvokeOutputFormat.JSON:
            self.assertEqual(list(result), [RemoteInvokeResponse(mock_json_response)])
        else:
            self.assertEqual(list(result), [RemoteInvokeResponse(mock_text_response)])

        self.kinesis_client.put_record.assert_called_with(
            Data=given_input_data, StreamName=self.stream_name, PartitionKey=mock_uuid_value
        )

    @parameterized.expand(
        [
            ({}, {"PartitionKey": "mock-uuid-value"}),
            (
                {"ExplicitHashKey": "mock-explicit-hash-key", "SequenceNumberForOrdering": "1"},
                {
                    "PartitionKey": "mock-uuid-value",
                    "ExplicitHashKey": "mock-explicit-hash-key",
                    "SequenceNumberForOrdering": "1",
                },
            ),
            (
                {
                    "PartitionKey": "override-partition-key",
                },
                {
                    "PartitionKey": "override-partition-key",
                },
            ),
            (
                {"StreamName": "mock-stream-name", "Data": "mock-data"},
                {"PartitionKey": "mock-uuid-value"},
            ),
            (
                {"invalidParameterKey": "invalidParameterValue"},
                {"invalidParameterKey": "invalidParameterValue", "PartitionKey": "mock-uuid-value"},
            ),
        ]
    )
    @patch("samcli.lib.remote_invoke.kinesis_invoke_executors.uuid")
    def test_validate_action_parameters(self, parameters, expected_boto_parameters, patched_uuid):
        mock_uuid_value = "mock-uuid-value"
        patched_uuid.uuid4.return_value = mock_uuid_value
        self.kinesis_put_data_executor.validate_action_parameters(parameters)
        self.assertEqual(self.kinesis_put_data_executor.request_parameters, expected_boto_parameters)

    @parameterized.expand(
        [
            (ParamValidationError(report="Invalid parameters"), InvalidResourceBotoParameterException),
            (
                ClientError(error_response={"Error": {"Code": "MockException"}}, operation_name="send_message"),
                ErrorBotoApiCallException,
            ),
        ]
    )
    def test_execute_action_put_record_throws_boto_errors(self, boto_error, expected_error_thrown):
        given_input_message = "hello world"
        self.kinesis_client.put_record.side_effect = boto_error
        with self.assertRaises(expected_error_thrown):
            self.kinesis_put_data_executor.validate_action_parameters({})
            for _ in self.kinesis_put_data_executor._execute_action(given_input_message):
                pass
