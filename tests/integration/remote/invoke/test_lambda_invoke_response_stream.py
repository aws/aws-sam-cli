import json
import uuid

from tests.integration.remote.invoke.remote_invoke_integ_base import RemoteInvokeIntegBase
from tests.testing_utils import run_command

from pathlib import Path
import pytest


@pytest.mark.xdist_group(name="sam_remote_invoke_lambda_response_streaming")
class TestInvokeResponseStreamingLambdas(RemoteInvokeIntegBase):
    template = Path("template-lambda-response-streaming-fns.yaml")

    @classmethod
    def tearDownClass(cls):
        # Delete the deployed stack
        cls.cfn_client.delete_stack(StackName=cls.stack_name)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stack_name = f"{TestInvokeResponseStreamingLambdas.__name__}-{uuid.uuid4().hex}"
        cls.create_resources_and_boto_clients()

    def test_invoke_empty_event_provided(self):
        command_list = self.get_command_list(stack_name=self.stack_name, resource_id="NodeStreamingFunction")

        expected_streamed_responses = "LambdaFunctionStreamingResponsesTestDone!"
        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = remote_invoke_result.stdout.strip().decode()
        self.assertIn(expected_streamed_responses, remote_invoke_result_stdout)

    def test_invoke_with_only_event_provided(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            resource_id="NodeStreamingFunction",
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
        )

        expected_streamed_responses = "LambdaFunctionStreamingResponsesTestDone!"
        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = remote_invoke_result.stdout.strip().decode()
        self.assertIn(expected_streamed_responses, remote_invoke_result_stdout)

    def test_invoke_with_only_event_file_provided(self):
        event_file_path = str(self.events_folder_path.joinpath("default_event.json"))
        command_list = self.get_command_list(
            stack_name=self.stack_name, resource_id="NodeStreamingEventValuesFunction", event_file=event_file_path
        )

        expected_streamed_responses = "Helloserverlessworld"
        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = remote_invoke_result.stdout.strip().decode()

        self.assertEqual(expected_streamed_responses, remote_invoke_result_stdout)

    def test_invoke_json_output_option(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
            resource_id="NodeStreamingEventValuesFunction",
            output="json",
            parameter_list=[("LogType", "None")],
        )

        remote_invoke_result = run_command(command_list)
        expected_output_result = [
            {"PayloadChunk": {"Payload": "Hello"}},
            {"PayloadChunk": {"Payload": "serverless"}},
            {"PayloadChunk": {"Payload": "world"}},
            {"InvokeComplete": {}},
        ]

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        response_event_stream = remote_invoke_result_stdout["EventStream"]
        self.assertEqual(response_event_stream, expected_output_result)

    def test_invoke_different_boto_options(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
            resource_id="NodeStreamingEventValuesFunction",
            output="json",
            parameter_list=[("LogType", "None"), ("InvocationType", "DryRun"), ("Qualifier", "$LATEST")],
        )

        remote_invoke_result = run_command(command_list)
        expected_output_result = [
            {"PayloadChunk": {"Payload": "Hello"}},
            {"PayloadChunk": {"Payload": "serverless"}},
            {"PayloadChunk": {"Payload": "world"}},
            {"InvokeComplete": {}},
        ]

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())

        response_event_stream = remote_invoke_result_stdout["EventStream"]
        self.assertEqual(response_event_stream, expected_output_result)