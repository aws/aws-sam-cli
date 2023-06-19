import json
import uuid
import base64

from parameterized import parameterized

from tests.integration.remote.invoke.remote_invoke_integ_base import RemoteInvokeIntegBase
from tests.testing_utils import run_command

from pathlib import Path
import pytest


@pytest.mark.xdist_group(name="sam_remote_invoke_single_lambda_resource")
class TestSingleResourceInvoke(RemoteInvokeIntegBase):
    template = Path("template-single-lambda.yaml")

    @classmethod
    def tearDownClass(cls):
        # Delete the deployed stack
        cls.cfn_client.delete_stack(StackName=cls.stack_name)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stack_name = f"{TestSingleResourceInvoke.__name__}-{uuid.uuid4().hex}"
        cls.create_resources_and_boto_clients()

    def test_invoke_empty_event_provided(self):
        command_list = self.get_command_list(stack_name=self.stack_name)

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout["errorType"], "KeyError")

    def test_invoke_with_only_event_provided(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, {"message": "Hello world"})

    def test_invoke_with_only_event_file_provided(self):
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
        lambda_name = self.stack_resources[resource_id]
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


@pytest.mark.xdist_group(name="sam_remote_invoke_multiple_resources")
class TestMultipleResourcesInvoke(RemoteInvokeIntegBase):
    template = Path("template-multiple-resources.yaml")

    @classmethod
    def tearDownClass(cls):
        # Delete the deployed stack
        cls.cfn_client.delete_stack(StackName=cls.stack_name)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stack_name = f"{TestMultipleResourcesInvoke.__name__}-{uuid.uuid4().hex}"
        cls.create_resources_and_boto_clients()

    def test_invoke_empty_event_provided(self):
        command_list = self.get_command_list(stack_name=self.stack_name, resource_id="EchoEventFunction")

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, {})

    @parameterized.expand(
        [
            ("HelloWorldServerlessFunction", {"message": "Hello world"}),
            ("EchoCustomEnvVarFunction", "MyOtherVar"),
            ("EchoEventFunction", {"key1": "Hello", "key2": "serverless", "key3": "world"}),
        ]
    )
    def test_invoke_with_only_event_provided(self, resource_id, expected_response):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            resource_id=resource_id,
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
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
    def test_invoke_with_resource_id_provided_as_arn(self, resource_id, expected_response):
        lambda_name = self.stack_resources[resource_id]
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
        command_list = RemoteInvokeIntegBase.get_command_list(
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


@pytest.mark.xdist_group(name="sam_remote_invoke_nested_resources")
class TestNestedTemplateResourcesInvoke(RemoteInvokeIntegBase):
    template = Path("nested_templates/template.yaml")

    @classmethod
    def tearDownClass(cls):
        # Delete the deployed stack
        cls.cfn_client.delete_stack(StackName=cls.stack_name)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stack_name = f"{TestNestedTemplateResourcesInvoke.__name__}-{uuid.uuid4().hex}"
        cls.create_resources_and_boto_clients()

    def test_invoke_empty_event_provided(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
        )

        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, {"message": "Hello world"})

    def test_invoke_with_only_event_provided(self):
        command_list = self.get_command_list(
            stack_name=self.stack_name,
            resource_id="ChildStack/HelloWorldFunction",
            event='{"key1": "Hello", "key2": "serverless", "key3": "world"}',
        )

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, {"message": "Hello world"})

    def test_invoke_default_lambda_function(self):
        event_file_path = str(self.events_folder_path.joinpath("default_event.json"))
        command_list = self.get_command_list(stack_name=self.stack_name, event_file=event_file_path)

        remote_invoke_result = run_command(command_list)

        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_result_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        self.assertEqual(remote_invoke_result_stdout, {"message": "Hello world"})
