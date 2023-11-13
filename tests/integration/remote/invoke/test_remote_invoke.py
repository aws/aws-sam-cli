import json
import uuid
import base64
import time
import math

from parameterized import parameterized
from unittest import skip

from tests.integration.remote.invoke.remote_invoke_integ_base import RemoteInvokeIntegBase
from tests.testing_utils import run_command

from pathlib import Path
import pytest

SQS_WAIT_TIME_SECONDS = 20


@pytest.mark.xdist_group(name="sam_remote_invoke_single_lambda_resource")
class TestSingleLambdaInvoke(RemoteInvokeIntegBase):
    template = Path("template-single-lambda.yaml")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stack_name = f"{cls.__name__}-{uuid.uuid4().hex}"
        cls.create_resources_and_boto_clients()

    def test_invoke_empty_event_provided(self):
        command_list = self.get_command_list(stack_name=self.stack_name)

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout["errorType"], "KeyError")

    def test_invoke_with_event_provided(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, {"message": "Hello world"})

    def test_invoke_with_event_file_provided(self):
        event_file_path = str(self.events_folder_path.joinpath("default_event.json"))
        command_list = self.get_command_list(
            stack_name=self.stack_name, resource_id="HelloWorldFunction", event_file=event_file_path
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, {"message": "Hello world"})

    def test_invoke_with_resource_id_provided_as_arn(self):
        resource_id = "HelloWorldFunction"
        lambda_name = self.stack_resource_summaries[resource_id].physical_resource_id
        lambda_arn = self.lambda_client.get_function(FunctionName=lambda_name)["Configuration"]["FunctionArn"]

        command_list = self.get_command_list(
            resource_id=lambda_arn,
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, {"message": "Hello world"})

    def test_invoke_asynchronous_using_boto_parameter(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
            parameter_list=[("InvocationType", "Event"), ("LogType", "None")],
            output="json",
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout["Payload"], "")
        self.assertEqual(remote_invoke_result_stdout["StatusCode"], 202)

    def test_invoke_dryrun_using_boto_parameter(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
            parameter_list=[("InvocationType", "DryRun"), ("Qualifier", "$LATEST")],
            output="json",
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout["Payload"], "")
        self.assertEqual(remote_invoke_result_stdout["StatusCode"], 204)

    def test_invoke_response_json_output_format(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
            output="json",
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        response_payload = json.loads(remote_invoke_result_stdout["Payload"])
        self.assertEqual(response_payload, {"message": "Hello world"})
        self.assertEqual(remote_invoke_result_stdout["StatusCode"], 200)


@pytest.mark.xdist_group(name="sam_remote_invoke_sfn_resource_priority")
class TestSFNPriorityInvoke(RemoteInvokeIntegBase):
    template = Path("template-step-function-priority.yaml")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stack_name = f"{cls.__name__}-{uuid.uuid4().hex}"
        cls.create_resources_and_boto_clients()

    def test_invoke_empty_event_provided(self):
        command_list = self.get_command_list(stack_name=self.stack_name)
        expected_response = "Hello World"

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, expected_response)

    @parameterized.expand(
        [('{"is_developer": false}', "Hello World"), ('{"is_developer": true}', "Hello Developer World")]
    )
    def test_invoke_with_event_provided(self, event, expected_response):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event=event,
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, expected_response)

    def test_invoke_with_event_file_provided(self):
        event_file_path = str(self.events_folder_path.joinpath("sfn_input_event.json"))
        expected_response = "Hello Developer World"
        command_list = self.get_command_list(stack_name=self.stack_name, event_file=event_file_path)

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, expected_response)

    def test_invoke_boto_parameters(self):
        expected_response = "Hello World"
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event='{"is_developer": false}',
            parameter_list=[("name", "custom-execution-name"), ("traceHeader", "Root=not enabled;Sampled=0")],
            output="json",
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(json.loads(remote_invoke_result_stdout["output"]), expected_response)

        # Overriding traceHeader with not enabled will return a dummy value
        dummy_trace_id_returned = remote_invoke_result_stdout["traceHeader"][5:40]
        time.sleep(3)

        get_xrays_response = self.xray_client.batch_get_traces(TraceIds=[dummy_trace_id_returned])
        self.assertEqual([], get_xrays_response["Traces"])


@pytest.mark.xdist_group(name="sam_remote_invoke_sqs_resource_priority")
class TestSQSPriorityInvoke(RemoteInvokeIntegBase):
    template = Path("template-sqs-priority.yaml")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stack_name = f"{cls.__name__}-{uuid.uuid4().hex}"
        cls.create_resources_and_boto_clients()
        cls.sqs_queue_url = cls.stack_resource_summaries["MySQSQueue"].physical_resource_id

    def test_invoke_empty_event_provided(self):
        command_list = self.get_command_list(stack_name=self.stack_name)
        expected_message_body = "{}"

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertIn("MD5OfMessageBody", remote_invoke_result_stdout)
        self.assertIn("MessageId", remote_invoke_result_stdout)

        received_message_response = self.sqs_client.receive_message(
            QueueUrl=self.sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=SQS_WAIT_TIME_SECONDS
        ).get("Messages")
        self.assertEqual(len(received_message_response), 1)
        received_message = received_message_response[0]
        self.assertEqual(expected_message_body, received_message.get("Body"))
        self.assertEqual(received_message["MessageId"], remote_invoke_result_stdout["MessageId"])
        self.sqs_client.delete_message(QueueUrl=self.sqs_queue_url, ReceiptHandle=received_message["ReceiptHandle"])

    @parameterized.expand([('{"foo": "bar"}'), ("Hello World"), ("<heading>Reminder</heading>")])
    def test_invoke_with_event_provided(self, event):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event=event,
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertIn("MD5OfMessageBody", remote_invoke_result_stdout)
        self.assertIn("MessageId", remote_invoke_result_stdout)

        received_message_response = self.sqs_client.receive_message(
            QueueUrl=self.sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=SQS_WAIT_TIME_SECONDS
        ).get("Messages")
        self.assertEqual(len(received_message_response), 1)
        received_message = received_message_response[0]
        self.assertEqual(event, received_message.get("Body"))
        self.assertEqual(received_message["MessageId"], remote_invoke_result_stdout["MessageId"])
        self.sqs_client.delete_message(QueueUrl=self.sqs_queue_url, ReceiptHandle=received_message["ReceiptHandle"])

    def test_invoke_with_event_file_provided(self):
        event_file_path = str(self.events_folder_path.joinpath("default_event.json"))
        command_list = self.get_command_list(stack_name=self.stack_name, event_file=event_file_path)

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertIn("MD5OfMessageBody", remote_invoke_result_stdout)
        self.assertIn("MessageId", remote_invoke_result_stdout)

        received_message_response = self.sqs_client.receive_message(
            QueueUrl=self.sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=SQS_WAIT_TIME_SECONDS
        ).get("Messages")
        self.assertEqual(len(received_message_response), 1)
        received_message = received_message_response[0]
        self.assertEqual(received_message["MessageId"], remote_invoke_result_stdout["MessageId"])
        with open(event_file_path, "r") as f:
            expected_message = f.read()
            self.assertEqual(expected_message, received_message.get("Body"))
        self.sqs_client.delete_message(QueueUrl=self.sqs_queue_url, ReceiptHandle=received_message["ReceiptHandle"])

    def test_invoke_with_physical_id_provided_as_resource_id(self):
        event = '{"foo": "bar"}'
        command_list = self.get_command_list(
            resource_id=self.sqs_queue_url,
            event=event,
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertIn("MD5OfMessageBody", remote_invoke_result_stdout)
        self.assertIn("MessageId", remote_invoke_result_stdout)

        received_message_response = self.sqs_client.receive_message(
            QueueUrl=self.sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=SQS_WAIT_TIME_SECONDS
        ).get("Messages")
        self.assertEqual(len(received_message_response), 1)
        received_message = received_message_response[0]
        self.assertEqual(event, received_message.get("Body"))
        self.assertEqual(received_message["MessageId"], remote_invoke_result_stdout["MessageId"])
        self.sqs_client.delete_message(QueueUrl=self.sqs_queue_url, ReceiptHandle=received_message["ReceiptHandle"])

    def test_invoke_boto_parameters(self):
        given_message = "Hello World"
        message_attributes = {
            "City": {"DataType": "String", "StringValue": "Any City"},
            "Population": {"DataType": "Number", "StringValue": "1250800"},
        }
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event=given_message,
            parameter_list=[
                (
                    "MessageAttributes",
                    json.dumps(message_attributes),
                ),
                ("DelaySeconds", "1"),
                ("MessageSystemAttributes", "{}"),
            ],
            output="json",
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertIn("MD5OfMessageBody", remote_invoke_result_stdout)
        self.assertIn("MessageId", remote_invoke_result_stdout)
        self.assertIn("MD5OfMessageAttributes", remote_invoke_result_stdout)
        self.assertIn("ResponseMetadata", remote_invoke_result_stdout)

        time.sleep(1)  # Required as DelaySeconds is set to 1 and message cannot be received before this.
        received_message_response = self.sqs_client.receive_message(
            QueueUrl=self.sqs_queue_url,
            MaxNumberOfMessages=1,
            MessageAttributeNames=["All"],
            WaitTimeSeconds=SQS_WAIT_TIME_SECONDS,
        ).get("Messages")

        self.assertEqual(len(received_message_response), 1)
        received_message = received_message_response[0]
        self.assertEqual(received_message["MessageId"], remote_invoke_result_stdout["MessageId"])
        self.assertEqual(received_message.get("Body"), given_message)
        self.assertEqual(received_message.get("MessageAttributes"), message_attributes)
        self.sqs_client.delete_message(QueueUrl=self.sqs_queue_url, ReceiptHandle=received_message["ReceiptHandle"])


@pytest.mark.xdist_group(name="sam_remote_invoke_kinesis_resource_priority")
class TestKinesisPriorityInvoke(RemoteInvokeIntegBase):
    template = Path("template-kinesis-priority.yaml")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stack_name = f"{cls.__name__}-{uuid.uuid4().hex}"
        cls.create_resources_and_boto_clients()
        cls.stream_name = cls.stack_resource_summaries["KinesisStream"].physical_resource_id

    def test_invoke_empty_event_provided(self):
        command_list = self.get_command_list(stack_name=self.stack_name)
        expected_message_body = "{}"

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        self.assertIn("SequenceNumber", remote_invoke_result_stdout)
        self.assertIn("ShardId", remote_invoke_result_stdout)

        response_record = self.get_kinesis_records(
            remote_invoke_result_stdout["ShardId"], remote_invoke_result_stdout["SequenceNumber"], self.stream_name
        )[0]

        received_data = response_record["Data"].decode()
        self.assertEqual(received_data, expected_message_body)

    @parameterized.expand([('{"foo": "bar"}'), ('"Hello World"'), '{"hello": "world", "foo": 1, "bar": {}}'])
    def test_invoke_with_event_provided(self, event):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event=event,
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        self.assertIn("SequenceNumber", remote_invoke_result_stdout)
        self.assertIn("ShardId", remote_invoke_result_stdout)

        response_record = self.get_kinesis_records(
            remote_invoke_result_stdout["ShardId"], remote_invoke_result_stdout["SequenceNumber"], self.stream_name
        )[0]

        received_data = response_record["Data"].decode()
        self.assertEqual(received_data, event)

    def test_invoke_with_event_file_provided(self):
        event_file_path = str(self.events_folder_path.joinpath("default_event.json"))
        command_list = self.get_command_list(stack_name=self.stack_name, event_file=event_file_path)

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        self.assertIn("SequenceNumber", remote_invoke_result_stdout)
        self.assertIn("ShardId", remote_invoke_result_stdout)

        response_record = self.get_kinesis_records(
            remote_invoke_result_stdout["ShardId"], remote_invoke_result_stdout["SequenceNumber"], self.stream_name
        )[0]

        received_data = response_record["Data"].decode()
        with open(event_file_path, "r") as f:
            expected_message = f.read()
            self.assertEqual(received_data, expected_message)

    def test_invoke_with_physical_id_provided_as_resource_id(self):
        event = '{"foo": "bar"}'
        command_list = self.get_command_list(
            resource_id=self.stream_name,
            event=event,
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        self.assertIn("SequenceNumber", remote_invoke_result_stdout)
        self.assertIn("ShardId", remote_invoke_result_stdout)

        response_record = self.get_kinesis_records(
            remote_invoke_result_stdout["ShardId"], remote_invoke_result_stdout["SequenceNumber"], self.stream_name
        )[0]

        received_data = response_record["Data"].decode()
        self.assertEqual(received_data, event)

    def test_invoke_boto_parameters(self):
        event = '{"foo": "bar"}'
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event=event,
            parameter_list=[
                (
                    "PartitionKey",
                    "override-partition-key",
                ),
                ("SequenceNumberForOrdering", "0"),
            ],
            output="json",
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        self.assertIn("SequenceNumber", remote_invoke_result_stdout)
        self.assertIn("ShardId", remote_invoke_result_stdout)
        self.assertIn("ResponseMetadata", remote_invoke_result_stdout)

        response_record = self.get_kinesis_records(
            remote_invoke_result_stdout["ShardId"], remote_invoke_result_stdout["SequenceNumber"], self.stream_name
        )[0]

        received_data = response_record["Data"].decode()
        self.assertEqual(received_data, event)


@pytest.mark.xdist_group(name="sam_remote_invoke_multiple_resources")
class TestMultipleResourcesInvoke(RemoteInvokeIntegBase):
    template = Path("template-multiple-resources.yaml")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stack_name = f"{cls.__name__}-{uuid.uuid4().hex}"
        cls.create_resources_and_boto_clients()

    def test_invoke_empty_event_provided(self):
        resource_id = "EchoEventFunction"
        command_list = self.get_command_list(stack_name=self.stack_name, resource_id=resource_id)

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, {})

    @parameterized.expand(
        [
            (
                "HelloWorldServerlessFunction",
                '{"key1": "Hello", "key2": "serverless", "key3": "world"}',
                {"message": "Hello world"},
            ),
            ("EchoCustomEnvVarFunction", '{"key1": "Hello", "key2": "serverless", "key3": "world"}', "MyOtherVar"),
            (
                "EchoEventFunction",
                '{"key1": "Hello", "key2": "serverless", "key3": "world"}',
                {"key1": "Hello", "key2": "serverless", "key3": "world"},
            ),
            ("StockPriceGuideStateMachine", '{"stock_price": 60, "balance": 200, "qty": 2}', {"balance": 320}),
            ("StockPriceGuideStateMachine", '{"stock_price": 30, "balance": 200, "qty": 2}', {"balance": 140}),
        ]
    )
    def test_invoke_with_only_event_provided(self, resource_id, event, expected_response):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            resource_id=resource_id,
            event=event,
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, expected_response)

    @parameterized.expand(
        [
            ("HelloWorldServerlessFunction", {"message": "Hello world"}),
            ("EchoCustomEnvVarFunction", "MyOtherVar"),
            ("EchoEventFunction", {"key1": "Hello", "key2": "serverless", "key3": "world"}),
        ]
    )
    def test_lambda_invoke_with_resource_id_provided_as_arn(self, resource_id, expected_response):
        lambda_name = self.stack_resource_summaries[resource_id].physical_resource_id
        lambda_arn = self.lambda_client.get_function(FunctionName=lambda_name)["Configuration"]["FunctionArn"]

        command_list = self.get_command_list(
            resource_id=lambda_arn,
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, expected_response)

    def test_lambda_writes_to_stderr_invoke(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            resource_id="WriteToStderrFunction",
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = remote_invoke_result.stdout.strip().decode()
        remote_invoke_result_stderr = remote_invoke_result.stderr.strip().decode()
        self.assertIn("Lambda Function is writing to stderr", remote_invoke_result_stderr)
        self.assertEqual('"wrote to stderr"', remote_invoke_result_stdout)

    def test_lambda_raises_exception_invoke(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            resource_id="RaiseExceptionFunction",
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stderr = remote_invoke_result.stderr.strip().decode()
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        self.assertIn("Lambda is raising an exception", remote_invoke_result_stderr)
        self.assertEqual("Lambda is raising an exception", remote_invoke_result_stdout["errorMessage"])

    def test_lambda_invoke_client_context_boto_parameter(self):
        custom_json_str = {"custom": {"foo": "bar", "baz": "quzz"}}
        client_context_base64_str = base64.b64encode(json.dumps(custom_json_str).encode()).decode("utf-8")

        command_list = self.get_command_list(
            stack_name=self.stack_name,
            resource_id="EchoClientContextData",
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
            parameter_list=[("ClientContext", client_context_base64_str)],
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, custom_json_str["custom"])

    def test_sfn_invoke_with_resource_id_provided_as_arn(self):
        resource_id = "StockPriceGuideStateMachine"
        expected_response = {"balance": 320}
        state_machine_arn = self.stack_resource_summaries[resource_id].physical_resource_id

        command_list = self.get_command_list(
            resource_id=state_machine_arn,
            event='{"stock_price": 60, "balance": 200, "qty": 2}',
        )
        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, expected_response)

    def test_sfn_invoke_boto_parameters(self):
        resource_id = "StockPriceGuideStateMachine"
        expected_response = {"balance": 320}
        name = "custom-execution-name"
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            resource_id=resource_id,
            event='{"stock_price": 60, "balance": 200, "qty": 2}',
            parameter_list=[("name", name)],
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, expected_response)

    def test_sfn_invoke_execution_fails(self):
        resource_id = "StateMachineExecutionFails"
        expected_response = "The execution failed due to the error: MockError and cause: Mock Invalid response."
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            resource_id=resource_id,
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
        )

        remote_invoke_result = run_command(command_list)
        remote_invoke_stderr = remote_invoke_result.stderr.strip().decode()

        self.assertEqual(0, remote_invoke_result.process.returncode)
        self.assertIn(expected_response, remote_invoke_stderr)

    def test_sqs_invoke_with_resource_id_and_stack_name(self):
        resource_id = "MySQSQueue"
        given_message = "Hello world"
        sqs_queue_url = self.stack_resource_summaries[resource_id].physical_resource_id

        command_list = self.get_command_list(
            resource_id=resource_id,
            stack_name=self.stack_name,
            event=given_message,
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertIn("MD5OfMessageBody", remote_invoke_result_stdout)
        self.assertIn("MessageId", remote_invoke_result_stdout)

        received_message_response = self.sqs_client.receive_message(
            QueueUrl=sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=SQS_WAIT_TIME_SECONDS
        ).get("Messages")
        self.assertEqual(len(received_message_response), 1)
        received_message = received_message_response[0]
        self.assertEqual(given_message, received_message.get("Body"))
        self.assertEqual(received_message["MessageId"], remote_invoke_result_stdout["MessageId"])
        self.sqs_client.delete_message(QueueUrl=sqs_queue_url, ReceiptHandle=received_message["ReceiptHandle"])

    def test_sqs_invoke_with_resource_id_provided_as_arn(self):
        resource_logical_id = "MySQSQueue"

        output = self.cfn_client.describe_stacks(StackName=self.stack_name)
        sqs_queue_arn = None
        sqs_queue_url = self.stack_resource_summaries[resource_logical_id].physical_resource_id
        for detail in output["Stacks"][0]["Outputs"]:
            if detail["OutputKey"] == "MySQSQueueArn":
                sqs_queue_arn = detail["OutputValue"]

        given_message = "Hello world"

        command_list = self.get_command_list(
            resource_id=sqs_queue_arn,
            event=given_message,
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertIn("MD5OfMessageBody", remote_invoke_result_stdout)
        self.assertIn("MessageId", remote_invoke_result_stdout)

        received_message_response = self.sqs_client.receive_message(
            QueueUrl=sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=SQS_WAIT_TIME_SECONDS
        ).get("Messages")
        self.assertEqual(len(received_message_response), 1)
        received_message = received_message_response[0]
        self.assertEqual(given_message, received_message.get("Body"))
        self.assertEqual(received_message["MessageId"], remote_invoke_result_stdout["MessageId"])
        self.sqs_client.delete_message(QueueUrl=sqs_queue_url, ReceiptHandle=received_message["ReceiptHandle"])

    def test_sqs_invoke_boto_parameters_fifo_queue(self):
        given_message = "Hello World"
        resource_logical_id = "MyFIFOSQSQueue"

        sqs_queue_url = self.stack_resource_summaries[resource_logical_id].physical_resource_id
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            resource_id=resource_logical_id,
            event=given_message,
            parameter_list=[
                ("MessageGroupId", "test-message-group"),
                ("MessageDeduplicationId", "test-dedup-id"),
            ],
            output="json",
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)

        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertIn("MD5OfMessageBody", remote_invoke_result_stdout)
        self.assertIn("MessageId", remote_invoke_result_stdout)
        self.assertIn("ResponseMetadata", remote_invoke_result_stdout)

        received_message_response = self.sqs_client.receive_message(
            QueueUrl=sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=SQS_WAIT_TIME_SECONDS
        ).get("Messages")

        self.assertEqual(len(received_message_response), 1)
        received_message = received_message_response[0]
        self.assertEqual(received_message["MessageId"], remote_invoke_result_stdout["MessageId"])
        self.assertEqual(received_message.get("Body"), given_message)

        # Send the same message again to test dedup
        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)

        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        # Message id will be the same as it got deduped and a new message was not created
        self.assertEqual(received_message["MessageId"], remote_invoke_result_stdout["MessageId"])
        self.sqs_client.delete_message(QueueUrl=sqs_queue_url, ReceiptHandle=received_message["ReceiptHandle"])

    def test_kinesis_invoke_with_resource_id_and_stack_name(self):
        resource_logical_id = "KinesisStream"
        event = '{"foo": "bar"}'
        stream_name = self.stack_resource_summaries[resource_logical_id].physical_resource_id

        command_list = self.get_command_list(
            resource_id=resource_logical_id,
            stack_name=self.stack_name,
            event=event,
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        self.assertIn("SequenceNumber", remote_invoke_result_stdout)
        self.assertIn("ShardId", remote_invoke_result_stdout)

        response_record = self.get_kinesis_records(
            remote_invoke_result_stdout["ShardId"], remote_invoke_result_stdout["SequenceNumber"], stream_name
        )[0]

        received_data = response_record["Data"].decode()
        self.assertEqual(received_data, event)

    def test_kinesis_invoke_with_resource_id_provided_as_arn(self):
        resource_logical_id = "KinesisStream"

        stream_name = self.stack_resource_summaries[resource_logical_id].physical_resource_id
        output = self.cfn_client.describe_stacks(StackName=self.stack_name)
        kinesis_stream_arn = None
        for detail in output["Stacks"][0]["Outputs"]:
            if detail["OutputKey"] == "KinesisStreamArn":
                kinesis_stream_arn = detail["OutputValue"]

        event = '{"foo": "bar"}'
        command_list = self.get_command_list(
            resource_id=kinesis_stream_arn,
            event=event,
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        self.assertIn("SequenceNumber", remote_invoke_result_stdout)
        self.assertIn("ShardId", remote_invoke_result_stdout)

        response_record = self.get_kinesis_records(
            remote_invoke_result_stdout["ShardId"], remote_invoke_result_stdout["SequenceNumber"], stream_name
        )[0]

        received_data = response_record["Data"].decode()
        self.assertEqual(received_data, event)

    def test_kinesis_invoke_with_boto_parameters(self):
        # ExplicitHashKey can be used to specify the shard to put the record to if the hashkey provided is
        # between the start and end range of that shard's hash key range.
        resource_logical_id = "KinesisStream"
        stream_name = self.stack_resource_summaries[resource_logical_id].physical_resource_id

        describe_stream_response = self.kinesis_client.describe_stream(StreamName=stream_name)
        shards = describe_stream_response["StreamDescription"]["Shards"]
        specific_shard = shards[2]
        start_hash_key = int(specific_shard["HashKeyRange"]["StartingHashKey"])
        end_hash_key = int(specific_shard["HashKeyRange"]["EndingHashKey"])
        explicit_hash_key = math.floor((start_hash_key + end_hash_key) / 2)

        event = '{"foo": "bar"}'
        command_list = self.get_command_list(
            resource_id=resource_logical_id,
            stack_name=self.stack_name,
            event=event,
            parameter_list=[
                ("ExplicitHashKey", str(explicit_hash_key)),
            ],
            output="json",
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        self.assertIn("SequenceNumber", remote_invoke_result_stdout)
        self.assertIn("ShardId", remote_invoke_result_stdout)
        self.assertEqual(remote_invoke_result_stdout["ShardId"], specific_shard["ShardId"])
        self.assertIn("ResponseMetadata", remote_invoke_result_stdout)

        response_record = self.get_kinesis_records(
            remote_invoke_result_stdout["ShardId"], remote_invoke_result_stdout["SequenceNumber"], stream_name
        )[0]

        received_data = response_record["Data"].decode()
        self.assertEqual(received_data, event)


@pytest.mark.xdist_group(name="sam_remote_invoke_nested_resources")
class TestNestedTemplateResourcesInvoke(RemoteInvokeIntegBase):
    template = Path("nested_templates/template.yaml")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stack_name = f"{cls.__name__}-{uuid.uuid4().hex}"
        cls.create_resources_and_boto_clients()

    @parameterized.expand(
        [
            ("ChildStack/HelloWorldFunction", {"message": "Hello world"}),
            ("ChildStack/HelloWorldStateMachine", "World"),
        ]
    )
    def test_invoke_empty_event_provided(self, resource_id, expected_response):
        command_list = self.get_command_list(stack_name=self.stack_name, resource_id=resource_id)

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, expected_response)

    @parameterized.expand(
        [
            ("ChildStack/HelloWorldFunction", '{"key1": "Hello", "key2": "world"}', {"message": "Hello world"}),
            ("ChildStack/HelloWorldStateMachine", '{"key1": "Hello", "key2": "world"}', "World"),
        ]
    )
    def test_invoke_with_event_provided(self, resource_id, event, expected_response):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            resource_id=resource_id,
            event=event,
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, expected_response)

    def test_invoke_event_file_provided(self):
        event_file_path = str(self.events_folder_path.joinpath("default_event.json"))
        command_list = self.get_command_list(
            stack_name=self.stack_name, resource_id="ChildStack/HelloWorldFunction", event_file=event_file_path
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, {"message": "Hello world"})
