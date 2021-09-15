import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time

import boto3
import docker
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

from samcli.commands.local.cli_common.invoke_context import ContainersInitializationMode
from tests.integration.local.start_lambda.start_lambda_api_integ_base import CDKStartLambdaIntegPythonBase


class TestCDKLambdaService(CDKStartLambdaIntegPythonBase):
    template_path = "/testdata/invoke/cdk/python/aws-lambda-function"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client(
            "lambda",
            endpoint_url=self.url,
            region_name="us-east-1",
            use_ssl=False,
            verify=False,
            config=Config(signature_version=UNSIGNED, read_timeout=120, retries={"max_attempts": 0}),
        )

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_no_data(self):
        response = self.lambda_client.invoke(FunctionName="HelloWorldFunction")

        self.assertEqual(response.get("Payload").read().decode("utf-8"), '"Hello world!"')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_data(self):
        response = self.lambda_client.invoke(FunctionName="CDKEchoEventFunction", Payload='"This is json data"')

        self.assertEqual(response.get("Payload").read().decode("utf-8"), '"This is json data"')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_no_data_empty_response(self):
        response = self.lambda_client.invoke(FunctionName="CDKEchoEventFunction")

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "{}")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_log_type_None(self):
        response = self.lambda_client.invoke(FunctionName="CDKEchoEventFunction", LogType="None")

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "{}")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_invocation_type_RequestResponse(self):
        response = self.lambda_client.invoke(FunctionName="CDKEchoEventFunction", InvocationType="RequestResponse")

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "{}")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)


class TestLambdaServiceErrorCases(CDKStartLambdaIntegPythonBase):
    template_path = "/testdata/invoke/cdk/python/aws-lambda-function"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client(
            "lambda",
            endpoint_url=self.url,
            region_name="us-east-1",
            use_ssl=False,
            verify=False,
            config=Config(signature_version=UNSIGNED, read_timeout=120, retries={"max_attempts": 0}),
        )

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_non_json_data(self):
        expected_error_message = (
            "An error occurred (InvalidRequestContent) when calling the Invoke operation: "
            "Could not parse request body into json: No JSON object could be decoded"
        )

        with self.assertRaises(ClientError) as error:
            self.lambda_client.invoke(FunctionName="EchoEventFunction", Payload="notat:asdfasdf")

        self.assertEqual(str(error.exception), expected_error_message)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_log_type_not_None(self):
        expected_error_message = (
            "An error occurred (NotImplemented) when calling the Invoke operation: "
            "log-type: Tail is not supported. None is only supported."
        )

        with self.assertRaises(ClientError) as error:
            self.lambda_client.invoke(FunctionName="EchoEventFunction", LogType="Tail")

        self.assertEqual(str(error.exception), expected_error_message)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_invocation_type_not_RequestResponse(self):
        expected_error_message = (
            "An error occurred (NotImplemented) when calling the Invoke operation: "
            "invocation-type: DryRun is not supported. RequestResponse is only supported."
        )

        with self.assertRaises(ClientError) as error:
            self.lambda_client.invoke(FunctionName="EchoEventFunction", InvocationType="DryRun")

        self.assertEqual(str(error.exception), expected_error_message)


class TestParallelRequests(CDKStartLambdaIntegPythonBase):
    template_path = "/testdata/invoke/cdk/python/aws-lambda-function"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client(
            "lambda",
            endpoint_url=self.url,
            region_name="us-east-1",
            use_ssl=False,
            verify=False,
            config=Config(signature_version=UNSIGNED, read_timeout=120, retries={"max_attempts": 0}),
        )

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_same_endpoint(self):
        """
        Send two requests to the same path at the same time. This is to ensure we can handle
        multiple requests at once and do not block/queue up requests
        """
        number_of_requests = 10
        start_time = time()
        with ThreadPoolExecutor(number_of_requests) as thread_pool:
            futures = [
                thread_pool.submit(self.lambda_client.invoke, FunctionName="HelloWorldFunction")
                for _ in range(0, number_of_requests)
            ]
            results = [r.result() for r in as_completed(futures)]

            end_time = time()

            self.assertEqual(len(results), 10)
            self.assertGreater(end_time - start_time, 10)

            for result in results:
                self.assertEqual(result.get("Payload").read().decode("utf-8"), '"Hello world!"')


class TestWarmContainersBaseClass(CDKStartLambdaIntegPythonBase):
    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.docker_client = docker.from_env()
        self.lambda_client = boto3.client(
            "lambda",
            endpoint_url=self.url,
            region_name="us-east-1",
            use_ssl=False,
            verify=False,
            config=Config(signature_version=UNSIGNED, read_timeout=120, retries={"max_attempts": 0}),
        )

    def count_running_containers(self):
        running_containers = 0
        for container in self.docker_client.containers.list():
            _, output = container.exec_run(["bash", "-c", "'printenv'"])
            if f"MODE={self.mode_env_variable}" in str(output):
                running_containers += 1
        return running_containers


class TestWarmContainers(TestWarmContainersBaseClass):
    template_path = "/testdata/start_api/template-warm-containers.yaml"
    container_mode = ContainersInitializationMode.EAGER.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response, "Hello world!")


class TestWarmContainersInitialization(TestWarmContainersBaseClass):
    template_path = "/testdata/invoke/cdk/python/aws-lambda-function"
    container_mode = ContainersInitializationMode.EAGER.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_all_containers_are_initialized_before_any_invoke(self):
        initiated_containers = self.count_running_containers()
        self.assertEqual(initiated_containers, 2)


class TestLazyContainers(TestWarmContainersBaseClass):
    template_path = "/testdata/start_api/template-warm-containers.yaml"
    container_mode = ContainersInitializationMode.LAZY.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response, "Hello world!")


class TestLazyContainersInitialization(TestWarmContainersBaseClass):
    template_path = "/testdata/invoke/cdk/python/aws-lambda-function"
    container_mode = ContainersInitializationMode.LAZY.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_all_containers_are_initialized_before_any_invoke(self):
        initiated_containers = self.count_running_containers()
        self.assertEqual(initiated_containers, 0)


class TestLazyContainersMultipleInvoke(TestWarmContainersBaseClass):
    template_path = "/testdata/invoke/cdk/python/aws-lambda-function"
    container_mode = ContainersInitializationMode.LAZY.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_only_one_new_created_containers_after_lambda_function_invoke(self):
        initiated_containers_before_any_invoke = self.count_running_containers()
        self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        initiated_containers = self.count_running_containers()

        # only one container is initialized
        self.assertEqual(initiated_containers, initiated_containers_before_any_invoke + 1)
