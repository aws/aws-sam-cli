from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized, parameterized_class
from samcli.lib.remote_invoke.sqs_invoke_executors import (
    RemoteInvokeOutputFormat,
    SqsSendMessageExecutor,
    ParamValidationError,
    InvalidResourceBotoParameterException,
    ErrorBotoApiCallException,
    ClientError,
    SqsSendMessageTextOutput,
    get_queue_url_from_arn,
)
from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeResponse


class TestSqsSendMessageTextOutput(TestCase):
    @parameterized.expand(
        [
            ("mock-md5-message-body", "mock-message-id", "mock-md5-message-attributes"),
            ("mock-md5-message-body", "mock-message-id", None),
        ]
    )
    def test_sqs_send_message_text_output(self, md5_of_message_body, message_id, md5_of_message_attrs):
        text_output = SqsSendMessageTextOutput(
            MD5OfMessageBody=md5_of_message_body, MessageId=message_id, MD5OfMessageAttributes=md5_of_message_attrs
        )
        self.assertEqual(text_output.MD5OfMessageBody, md5_of_message_body)
        self.assertEqual(text_output.MessageId, message_id)
        self.assertEqual(text_output.MD5OfMessageAttributes, md5_of_message_attrs)

    @parameterized.expand(
        [
            (
                "mock-md5-message-body",
                "mock-message-id",
                "mock-md5-message-attributes",
                {
                    "MD5OfMessageBody": "mock-md5-message-body",
                    "MessageId": "mock-message-id",
                    "MD5OfMessageAttributes": "mock-md5-message-attributes",
                },
            ),
            (
                "mock-md5-message-body",
                "mock-message-id",
                None,
                {"MD5OfMessageBody": "mock-md5-message-body", "MessageId": "mock-message-id"},
            ),
        ]
    )
    def test_get_output_response_dict(self, md5_of_message_body, message_id, md5_of_message_attrs, expected_output):
        text_output = SqsSendMessageTextOutput(
            MD5OfMessageBody=md5_of_message_body, MessageId=message_id, MD5OfMessageAttributes=md5_of_message_attrs
        )
        output_response_dict = text_output.get_output_response_dict()
        self.assertEqual(output_response_dict, expected_output)


@parameterized_class(
    "output",
    [[RemoteInvokeOutputFormat.TEXT], [RemoteInvokeOutputFormat.JSON]],
)
class TestSqsSendMessageExecutor(TestCase):
    output: RemoteInvokeOutputFormat

    def setUp(self) -> None:
        self.sqs_client = Mock()
        self.sqs_url = "https://sqs.us-east-1.amazonaws.com/12345678910/mock-queue-name"
        self.sqs_send_message_executor = SqsSendMessageExecutor(self.sqs_client, self.sqs_url, self.output)

    def test_execute_action_successful(self):
        given_input_message = "hello world"
        mock_md5_message_body = "5eb63bbbe01eeed093cb22bb8f5acdc3"
        mock_message_id = "2941492a-5847-4ebb-a8a3-58c07ce9f198"
        mock_md5_message_attributes = "5eb63bbbe01eeed093cb22bb8f5acdc3"
        mock_text_response = {
            "MD5OfMessageBody": mock_md5_message_body,
            "MessageId": mock_message_id,
            "MD5OfMessageAttributes": mock_md5_message_attributes,
        }

        mock_json_response = {
            "MD5OfMessageBody": mock_md5_message_body,
            "MessageId": mock_message_id,
            "MD5OfMessageAttributes": mock_md5_message_attributes,
            "ResponseMetadata": {},
        }
        self.sqs_client.send_message.return_value = {
            "MD5OfMessageBody": mock_md5_message_body,
            "MessageId": mock_message_id,
            "MD5OfMessageAttributes": mock_md5_message_attributes,
            "ResponseMetadata": {},
        }
        self.sqs_send_message_executor.validate_action_parameters({})
        result = self.sqs_send_message_executor._execute_action(given_input_message)
        if self.output == RemoteInvokeOutputFormat.JSON:
            self.assertEqual(list(result), [RemoteInvokeResponse(mock_json_response)])
        else:
            self.assertEqual(list(result), [RemoteInvokeResponse(mock_text_response)])

        self.sqs_client.send_message.assert_called_with(MessageBody=given_input_message, QueueUrl=self.sqs_url)

    @parameterized.expand(
        [
            ({}, {}),
            (
                {"MessageGroupId": "mockMessageGroupId", "MessageDeduplicationId": "mockMessageDedupId"},
                {"MessageGroupId": "mockMessageGroupId", "MessageDeduplicationId": "mockMessageDedupId"},
            ),
            (
                {
                    "MessageAttributes": '{\
                        "City": {"DataType": "String", "StringValue": "Any City"},\
                        "Greeting": {"DataType": "Binary", "BinaryValue": "Hello, World!"},\
                        "Population": {"DataType": "Number", "StringValue": "1250800"}\
                    }',
                    "MessageSystemAttributes": '{\
                        "AWSTraceHeader": {"DataType": "String", "StringValue": "Root=1-5759e988-bd862e3fe1be46a994272793;"}\
                    }',
                },
                {
                    "MessageAttributes": {
                        "City": {"DataType": "String", "StringValue": "Any City"},
                        "Greeting": {"DataType": "Binary", "BinaryValue": "Hello, World!"},
                        "Population": {"DataType": "Number", "StringValue": "1250800"},
                    },
                    "MessageSystemAttributes": {
                        "AWSTraceHeader": {
                            "DataType": "String",
                            "StringValue": "Root=1-5759e988-bd862e3fe1be46a994272793;",
                        }
                    },
                },
            ),
            (
                {"MessageBody": "mock message body", "QueueUrl": "mock-queue-url", "DelaySeconds": "3"},
                {"DelaySeconds": 3},
            ),
            (
                {"invalidParameterKey": "invalidParameterValue"},
                {"invalidParameterKey": "invalidParameterValue"},
            ),
        ]
    )
    def test_validate_action_parameters(self, parameters, expected_boto_parameters):
        self.sqs_send_message_executor.validate_action_parameters(parameters)
        self.assertEqual(self.sqs_send_message_executor.request_parameters, expected_boto_parameters)

    @parameterized.expand(
        [
            (
                {"MessageBody": "mock message body", "QueueUrl": "mock-queue-url", "DelaySeconds": "non-int-value"},
                InvalidResourceBotoParameterException,
            ),
            (
                {"MessageAttributes": "[invalid-json-string]", "MessageGroupId": "mockMessageGroupId"},
                InvalidResourceBotoParameterException,
            ),
        ]
    )
    def test_validate_action_parameters_errors(self, parameters, expected_err):
        with self.assertRaises(expected_err):
            self.sqs_send_message_executor.validate_action_parameters(parameters)

    @parameterized.expand(
        [
            (ParamValidationError(report="Invalid parameters"), InvalidResourceBotoParameterException),
            (
                ClientError(error_response={"Error": {"Code": "MockException"}}, operation_name="send_message"),
                ErrorBotoApiCallException,
            ),
        ]
    )
    def test_execute_action_send_message_throws_boto_errors(self, boto_error, expected_error_thrown):
        given_input_message = "hello world"
        self.sqs_client.send_message.side_effect = boto_error
        with self.assertRaises(expected_error_thrown):
            self.sqs_send_message_executor.validate_action_parameters({})
            for _ in self.sqs_send_message_executor._execute_action(given_input_message):
                pass


class TestSQSInvokeExecutorUtilities(TestCase):
    def test_get_queue_url_from_arn_successful(self):
        given_sqs_client = Mock()
        expected_result = "mock-queue-url"
        given_sqs_client.get_queue_url.return_value = {"QueueUrl": expected_result}
        self.assertEqual(get_queue_url_from_arn(given_sqs_client, "mock-queue-name"), expected_result)

    def test_get_queue_url_from_arn_fails(self):
        given_sqs_client = Mock()
        given_sqs_client.get_queue_url.side_effect = ClientError({}, "operation")
        with self.assertRaises(ErrorBotoApiCallException):
            get_queue_url_from_arn(given_sqs_client, "mock-queue-name")
