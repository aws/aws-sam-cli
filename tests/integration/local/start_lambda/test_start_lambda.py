import signal
from unittest import skipIf, TestCase
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time, sleep
import json
from parameterized import parameterized, parameterized_class
from subprocess import Popen, PIPE
from pathlib import Path

import pytest
import random

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
from docker.errors import APIError

from samcli.commands.local.cli_common.invoke_context import ContainersInitializationMode
from tests.testing_utils import IS_WINDOWS, get_sam_command, kill_process
from tests.integration.local.common_utils import random_port, InvalidAddressException, wait_for_local_process
from .start_lambda_api_integ_base import StartLambdaIntegBaseClass, WatchWarmContainersIntegBaseClass


class TestParallelRequests(StartLambdaIntegBaseClass):
    template_path = "/testdata/invoke/template.yml"

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
                thread_pool.submit(self.lambda_client.invoke, FunctionName="HelloWorldSleepFunction")
                for _ in range(0, number_of_requests)
            ]
            results = [r.result() for r in as_completed(futures)]

            end_time = time()

            self.assertEqual(len(results), 10)
            self.assertGreater(end_time - start_time, 10)

            for result in results:
                self.assertEqual(result.get("Payload").read().decode("utf-8"), '"Slept for 10s"')


class TestLambdaServiceErrorCases(StartLambdaIntegBaseClass):
    template_path = "/testdata/invoke/template.yml"

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


class TestLambdaServiceWithInlineCode(StartLambdaIntegBaseClass):
    template_path = "/testdata/invoke/template-inlinecode.yaml"

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
    def test_invoke_function_with_inline_code(self):
        expected_error_message = (
            "An error occurred (NotImplemented) when calling the Invoke operation:"
            " Inline code is not supported for sam local commands. Please write your code in a separate file."
        )

        with self.assertRaises(ClientError) as error:
            self.lambda_client.invoke(FunctionName="InlineCodeServerlessFunction", Payload='"This is json data"')

        self.assertEqual(str(error.exception), expected_error_message)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_function_without_inline_code(self):
        response = self.lambda_client.invoke(
            FunctionName="NoInlineCodeServerlessFunction",
            Payload='"This is json data"',
        )

        self.assertEqual(response.get("Payload").read().decode("utf-8"), '"This is json data"')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)


@parameterized_class(
    ("template_path", "parent_path"),
    [
        ("/testdata/invoke/template.yml", ""),
        ("/testdata/invoke/nested-templates/template-parent.yaml", "SubApp/"),
    ],
)
class TestLambdaService(StartLambdaIntegBaseClass):
    parent_path = ""

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

    @parameterized.expand([("False"), ("True")])
    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_data(self, use_full_path):
        response = self.lambda_client.invoke(
            FunctionName=f"{self.parent_path if use_full_path == 'True' else ''}EchoEventFunction",
            Payload='"This is json data"',
        )

        self.assertEqual(response.get("Payload").read().decode("utf-8"), '"This is json data"')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @parameterized.expand([("False"), ("True")])
    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_no_data(self, use_full_path):
        response = self.lambda_client.invoke(
            FunctionName=f"{self.parent_path if use_full_path == 'True' else ''}EchoEventFunction"
        )

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "{}")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @parameterized.expand([("False"), ("True")])
    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_log_type_None(self, use_full_path):
        response = self.lambda_client.invoke(
            FunctionName=f"{self.parent_path if use_full_path == 'True' else ''}EchoEventFunction", LogType="None"
        )

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "{}")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_multi_tenant_function_with_tenant_id(self):
        response = self.lambda_client.invoke(
            FunctionName="MultiTenantFunction", TenantId="tenant-123", Payload='{"test": "data"}'
        )

        self.assertEqual(response.get("StatusCode"), 200)
        payload = json.loads(response.get("Payload").read().decode("utf-8"))

        # The response is wrapped in a Lambda response format
        self.assertEqual(payload.get("statusCode"), 200)
        body = json.loads(payload.get("body"))
        self.assertEqual(body.get("tenant_id"), "tenant-123")
        self.assertEqual(body.get("message"), "Hello from multi-tenant function")

    @parameterized.expand([("False"), ("True")])
    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_invocation_type_RequestResponse(self, use_full_path):
        response = self.lambda_client.invoke(
            FunctionName=f"{self.parent_path if use_full_path == 'True' else ''}EchoEventFunction",
            InvocationType="RequestResponse",
        )

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "{}")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_of_function_with_function_name_override(self):
        response = self.lambda_client.invoke(FunctionName="echo-func-name-override")

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "{}")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @parameterized.expand(
        [
            ("EchoCustomEnvVarWithFunctionNameDefinedFunction", "False"),
            ("EchoCustomEnvVarWithFunctionNameDefinedFunction", "True"),
            ("customname", "False"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_function_with_overrode_env_var_and_functionname_defined(self, function_name, use_full_path):
        response = self.lambda_client.invoke(
            FunctionName=f"{self.parent_path if use_full_path == 'True' else ''}{function_name}"
        )

        self.assertEqual(response.get("Payload").read().decode("utf-8"), '"MyVar"')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @parameterized.expand([("False"), ("True")])
    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_lambda_function_raised_error(self, use_full_path):
        response = self.lambda_client.invoke(
            FunctionName=f"{self.parent_path if use_full_path == 'True' else ''}RaiseExceptionFunction",
            InvocationType="RequestResponse",
        )
        response_data = json.loads(response.get("Payload").read().decode("utf-8"))

        self.assertEqual(response_data.get("errorMessage"), "Lambda is raising an exception")
        self.assertEqual(response_data.get("errorType"), "Exception")
        self.assertEqual(response.get("StatusCode"), 200)

    @parameterized.expand([("False"), ("True")])
    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_function_timeout(self, use_full_path):
        """
        This behavior does not match the actually Lambda Service. For functions that timeout, data returned like the
        following:
        {"errorMessage":"<timestamp> <request_id> Task timed out after 5.00 seconds"}

        For Local Lambda's, however, timeouts are an interrupt on the thread that runs invokes the function. Since the
        invoke is on a different thread, we do not (currently) have a way to communicate this back to the caller. So
        when a timeout happens locally, we do not add the FunctionError: Unhandled to the response and have an empty
        string as the data returned (because no data was found in stdout from the container).
        """
        response = self.lambda_client.invoke(
            FunctionName=f"{self.parent_path if use_full_path == 'True' else ''}TimeoutFunction"
        )

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @parameterized.expand([("False"), ("True")])
    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_function_timeout_using_lookup_value(self, use_full_path):
        """
        This behavior does not match the actually Lambda Service. For functions that timeout, data returned like the
        following:
        {"errorMessage":"<timestamp> <request_id> Task timed out after 5.00 seconds"}

        For Local Lambda's, however, timeouts are an interrupt on the thread that runs invokes the function. Since the
        invoke is on a different thread, we do not (currently) have a way to communicate this back to the caller. So
        when a timeout happens locally, we do not add the FunctionError: Unhandled to the response and have an empty
        string as the data returned (because no data was found in stdout from the container).
        """
        response = self.lambda_client.invoke(
            FunctionName=f"{self.parent_path if use_full_path == 'True' else ''}TimeoutFunctionUsingLookupValue"
        )

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)


class TestWarmContainersBaseClass(StartLambdaIntegBaseClass):
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

    def count_running_containers(self):
        """Count containers created by this test using Docker client directly."""
        # Use Docker client to find containers with SAM CLI labels
        try:
            # Get running containers with SAM CLI lambda container label
            sam_containers = self.docker_client.containers.list(
                all=False, filters={"label": "sam.cli.container.type=lambda"}
            )

            # Filter by our test's mode environment variable if possible
            test_containers = []
            for container in sam_containers:
                try:
                    container.reload()
                    env_vars = container.attrs.get("Config", {}).get("Env", [])
                    for env_var in env_vars:
                        if env_var.startswith("MODE=") and self.mode_env_variable in env_var:
                            test_containers.append(container)
                            break
                except Exception:
                    continue

            # If we found containers with our mode variable, return that count
            if test_containers:
                return len(test_containers)

            # Otherwise, return all SAM containers (fallback)
            return len(sam_containers)

        except Exception as e:
            # If we can't access Docker client, fall back to 0
            return 0

    def _parse_container_ids_from_output(self):
        """Parse container IDs from the service output."""
        container_ids = []
        if hasattr(self, "start_lambda_process_output") and self.start_lambda_process_output:
            for line in self.start_lambda_process_output.split("\n"):
                # Look for container IDs: "SAM_CONTAINER_ID: <container_id>"
                if "SAM_CONTAINER_ID:" in line:
                    parts = line.split("SAM_CONTAINER_ID:")
                    if len(parts) > 1:
                        container_id = parts[1].strip()
                        if container_id:
                            container_ids.append(container_id)
        return container_ids

    def tearDown(self) -> None:
        # Use a new container test UUID for the next test run to avoid
        # counting additional containers in the event of a retry
        self.mode_env_variable = str(uuid.uuid4())
        super().tearDown()


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestWarmContainers(TestWarmContainersBaseClass):
    container_mode = ContainersInitializationMode.EAGER.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})


@skipIf(IS_WINDOWS, "SIGTERM interrupt doesn't exist on Windows")
class TestWarmContainersHandlesSigTermInterrupt(TestWarmContainersBaseClass):
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
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        initiated_containers = self.count_running_containers()
        self.assertEqual(initiated_containers, 2)

        service_process = self.start_lambda_process
        service_process.send_signal(signal.SIGTERM)

        # Sleep for 10 seconds since this is the default time that Docker
        # allows for a process to handle a SIGTERM before sending a SIGKILL
        sleep(10)

        remaining_containers = self.count_running_containers()
        self.assertEqual(remaining_containers, 0)
        self.assertEqual(service_process.poll(), 0)


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestWarmContainersInitialization(TestWarmContainersBaseClass):
    container_mode = ContainersInitializationMode.EAGER.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_all_containers_are_initialized_before_any_invoke(self):
        initiated_containers = self.count_running_containers()
        # validate that there a container initialized for each lambda function
        self.assertEqual(initiated_containers, 2)


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestWarmContainersMultipleInvoke(TestWarmContainersBaseClass):
    container_mode = ContainersInitializationMode.EAGER.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_no_new_created_containers_after_lambda_function_invoke(self):
        initiated_containers_before_invoking_any_function = self.count_running_containers()
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        initiated_containers = self.count_running_containers()

        # validate that no new containers got created
        self.assertEqual(initiated_containers, initiated_containers_before_invoking_any_function)


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestLazyContainers(TestWarmContainersBaseClass):
    container_mode = ContainersInitializationMode.LAZY.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestLazyContainersInitialization(TestWarmContainersBaseClass):
    container_mode = ContainersInitializationMode.LAZY.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_no_container_is_initialized_before_any_invoke(self):
        initiated_containers = self.count_running_containers()

        # no container is initialized
        self.assertEqual(initiated_containers, 0)


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestLazyContainersMultipleInvoke(TestWarmContainersBaseClass):
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


class TestImagePackageType(StartLambdaIntegBaseClass):
    template_path = "/testdata/start_api/image_package_type/template.yaml"
    build_before_invoke = True
    tag = f"python-{random.randint(1000,2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})


class TestImagePackageTypeWithEagerWarmContainersMode(StartLambdaIntegBaseClass):
    template_path = "/testdata/start_api/image_package_type/template.yaml"
    container_mode = ContainersInitializationMode.EAGER.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000,2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})


class TestImagePackageTypeWithEagerLazyContainersMode(StartLambdaIntegBaseClass):
    template_path = "/testdata/start_api/image_package_type/template.yaml"
    container_mode = ContainersInitializationMode.LAZY.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000,2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})


class TestWatchingZipWarmContainers(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
    """
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """
    docker_file_content = ""
    container_mode = ContainersInitializationMode.EAGER.value

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        self._write_file_content(self.code_path, self.code_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})


class TestWatchingTemplateChangesNewLambdaFunctionAdded(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.11
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
  HelloWorldFunction2:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler2
      Runtime: python3.11
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
    
    
def handler2(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """

    docker_file_content = ""
    container_mode = ContainersInitializationMode.EAGER.value

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        with self.assertRaises(ClientError):
            self.lambda_client.invoke(FunctionName="HelloWorldFunction2")

        self._write_file_content(self.template_path, self.template_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction2")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})


class TestWatchingTemplateChangesLambdaFunctionRemoved(WatchWarmContainersIntegBaseClass):
    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.11
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
  HelloWorldFunction2:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler2
      Runtime: python3.11
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}


def handler2(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """

    docker_file_content = ""
    container_mode = ContainersInitializationMode.EAGER.value

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction2")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})

        self._write_file_content(self.template_path, self.template_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        with self.assertRaises(ClientError):
            self.lambda_client.invoke(FunctionName="HelloWorldFunction2")


class TestWatchingTemplateChangesLambdaFunctionChangeCodeUri(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main2.handler
      Runtime: python3.11
      CodeUri: dir
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
    """

    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """

    docker_file_content = ""
    container_mode = ContainersInitializationMode.EAGER.value

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        self._write_file_content(self.template_path, self.template_content_2)
        self._write_file_content(self.code_path2, self.code_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})


class TestWatchingImageWarmContainers(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}"""
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}"""
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.11
COPY main.py ./"""
    container_mode = ContainersInitializationMode.EAGER.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000, 2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        self._write_file_content(self.code_path, self.code_content_2)
        self.build()
        # wait till SAM got notified that the source code got changed
        sleep(30)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})


class TestWatchingTemplateChangesDockerFileLocationChanged(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile
        """
    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile2
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}"""
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}"""
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.11
COPY main.py ./"""
    container_mode = ContainersInitializationMode.EAGER.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000, 2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        self._write_file_content(self.template_path, self.template_content_2)
        self._write_file_content(self.code_path, self.code_content_2)
        self._write_file_content(self.docker_file_path2, self.docker_file_content)
        self.build()
        # wait till SAM got notified that the source code got changed
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})


class TestWatchingZipLazyContainers(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
    """
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """
    docker_file_content = ""
    container_mode = ContainersInitializationMode.LAZY.value

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        self._write_file_content(self.code_path, self.code_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})


class TestWatchingImageLazyContainers(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}"""
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}"""
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.11
COPY main.py ./"""
    container_mode = ContainersInitializationMode.LAZY.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000, 2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        self._write_file_content(self.code_path, self.code_content_2)
        self.build()
        # wait till SAM got notified that the source code got changed
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})


class TestWatchingTemplateChangesNewLambdaFunctionAddedLazyContainer(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.11
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
  HelloWorldFunction2:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler2
      Runtime: python3.11
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}


def handler2(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """

    docker_file_content = ""
    container_mode = ContainersInitializationMode.LAZY.value

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        with self.assertRaises(ClientError):
            self.lambda_client.invoke(FunctionName="HelloWorldFunction2")

        self._write_file_content(self.template_path, self.template_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction2")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})


class TestWatchingTemplateChangesLambdaFunctionRemovedLazyContainers(WatchWarmContainersIntegBaseClass):
    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.11
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
  HelloWorldFunction2:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler2
      Runtime: python3.11
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}


def handler2(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """

    docker_file_content = ""
    container_mode = ContainersInitializationMode.LAZY.value

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction2")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})

        self._write_file_content(self.template_path, self.template_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        with self.assertRaises(ClientError):
            self.lambda_client.invoke(FunctionName="HelloWorldFunction2")


class TestWatchingTemplateChangesLambdaFunctionChangeCodeUriLazyContainer(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main2.handler
      Runtime: python3.11
      CodeUri: dir
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
    """

    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """

    docker_file_content = ""
    container_mode = ContainersInitializationMode.LAZY.value

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        self._write_file_content(self.template_path, self.template_content_2)
        self._write_file_content(self.code_path2, self.code_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})


class TestWatchingTemplateChangesDockerFileLocationChangedLazyContainer(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile
        """
    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile2
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}"""
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}"""
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.11
COPY main.py ./"""
    container_mode = ContainersInitializationMode.LAZY.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000, 2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

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
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})

        self._write_file_content(self.template_path, self.template_content_2)
        self._write_file_content(self.code_path, self.code_content_2)
        self._write_file_content(self.docker_file_path2, self.docker_file_content)
        self.build()
        # wait till SAM got notified that the source code got changed
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/invoke/template.yml",),
        ("/testdata/invoke/nested-templates/template-parent.yaml",),
    ],
)
class TestLambdaServiceWithCustomInvokeImages(StartLambdaIntegBaseClass):
    invoke_image = [
        "amazon/aws-sam-cli-emulation-image-python3.9",
        "HelloWorldServerlessFunction=public.ecr.aws/sam/emulation-python3.9",
    ]

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
    def test_invoke_with_data_custom_invoke_images(self):
        response = self.lambda_client.invoke(FunctionName="EchoEventFunction", Payload='"This is json data"')

        self.assertEqual(response.get("Payload").read().decode("utf-8"), '"This is json data"')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)


class TestFunctionNameFilteringWithFilter(StartLambdaIntegBaseClass):
    """Test function name filtering with specific functions"""

    template_path = "/testdata/invoke/template.yml"
    function_logical_ids = ["EchoEventFunction", "HelloWorldServerlessFunction"]

    def setUp(self):
        self.url = f"http://127.0.0.1:{self.port}"
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
    def test_invoke_filtered_function(self):
        """Test invoking a function that is in the filter"""
        response = self.lambda_client.invoke(FunctionName="EchoEventFunction", Payload='"filtered test"')
        self.assertEqual(response.get("StatusCode"), 200)
        self.assertEqual(response.get("Payload").read().decode("utf-8"), '"filtered test"')
        self.assertIsNone(response.get("FunctionError"))

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_non_filtered_function(self):
        """Test invoking a function that is NOT in the filter returns ResourceNotFoundException"""
        with self.assertRaises(ClientError) as context:
            self.lambda_client.invoke(FunctionName="FunctionWithMetadata")
            self.assertIn("ResourceNotFound", str(context.exception))


class TestFunctionNameFilteringWarmContainersEager(TestWarmContainersBaseClass):
    """Test function filtering with EAGER warm containers"""

    template_path = "/testdata/start_api/template-warm-containers.yaml"
    container_mode = ContainersInitializationMode.EAGER.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}
    function_logical_ids = ["HelloWorldFunction"]

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_only_filtered_functions_have_containers(self):
        """Test that only filtered functions have containers pre-warmed in EAGER mode"""
        self.assertEqual(self.count_running_containers(), 1)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_invoke_filtered_function_with_eager_containers(self):
        """Test invoking filtered function with EAGER warm containers"""
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)
        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world"})


class TestFunctionNameFilteringWarmContainersLazy(TestWarmContainersBaseClass):
    """Test function filtering with LAZY warm containers"""

    template_path = "/testdata/start_api/template-warm-containers.yaml"
    container_mode = ContainersInitializationMode.LAZY.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}
    function_logical_ids = ["HelloWorldFunction"]

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_no_containers_before_invoke_with_lazy(self):
        """Test that no containers are initialized before invocation in LAZY mode"""
        self.assertEqual(self.count_running_containers(), 0)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_container_created_on_demand_for_filtered_function(self):
        """Test that container is created on-demand for filtered function in LAZY mode"""
        self.assertEqual(self.count_running_containers(), 0)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)
        self.assertEqual(self.count_running_containers(), 1)


class TestFunctionNameFilteringInvalidNames(TestCase):
    """Test error handling for invalid function names"""

    integration_dir = str(Path(__file__).resolve().parents[2])
    template_path = "/testdata/invoke/template.yml"

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invalid_function_names_error(self):
        """Test that invalid function names produce helpful error message at startup"""
        template = self.integration_dir + self.template_path
        command_list = [
            get_sam_command(),
            "local",
            "start-lambda",
            "InvalidFunction1",
            "InvalidFunction2",
            "-p",
            str(random_port()),
            "-t",
            template,
        ]

        process = Popen(command_list, stderr=PIPE, stdout=PIPE, cwd=str(Path(template).resolve().parents[0]))
        stdout, stderr = process.communicate(timeout=30)

        self.assertNotEqual(process.returncode, 0)
        error_output = stderr.decode("utf-8")
        # Should match sam local invoke error pattern: "function not found. Possible options in your template:"
        for expected in ["not found", "InvalidFunction1, InvalidFunction2", "Possible options in your template"]:
            self.assertIn(expected, error_output)


class TestCapacityProviderFunction(StartLambdaIntegBaseClass):
    """Test capacity provider functionality with a dedicated template"""

    template_path = "/testdata/invoke/template-capacity-provider.yml"

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
    def test_invoke_capacity_provider_function(self):
        """Test invoking a function with capacity provider configuration"""
        response = self.lambda_client.invoke(
            FunctionName="HelloWorldCapacityProviderFunction",
            Payload='{"key1": "value1", "key2": "value2", "key3": "value3"}',
        )
        self.assertEqual(response.get("StatusCode"), 200)
        self.assertIsNone(response.get("FunctionError"))
        response_data = json.loads(response.get("Payload").read().decode("utf-8"))
        self.assertEqual(response_data["statusCode"], 200)
        body = json.loads(response_data["body"])
        self.assertEqual(body["message"], "Hello world capacity provider")
        self.assertIn("max_concurrency", body)
