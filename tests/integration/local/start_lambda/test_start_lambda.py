import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time, sleep
import json
from parameterized import parameterized, parameterized_class

import pytest
import random

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

from samcli.commands.local.cli_common.invoke_context import ContainersInitializationMode
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

        print(response_data)

        self.assertEqual(
            response_data,
            {
                "errorMessage": "Lambda is raising an exception",
                "errorType": "Exception",
                "stackTrace": [
                    ["/var/task/main.py", 51, "raise_exception", 'raise Exception("Lambda is raising an exception")']
                ],
            },
        )
        self.assertEqual(response.get("FunctionError"), "Unhandled")
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
        running_containers = 0
        for container in self.docker_client.containers.list():
            _, output = container.exec_run(["bash", "-c", "'printenv'"])
            if f"MODE={self.mode_env_variable}" in str(output):
                running_containers += 1
        return running_containers


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
      Runtime: python3.6
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
      Runtime: python3.6
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
      Runtime: python3.7
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
      Runtime: python3.7
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
      Runtime: python3.6
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
      Runtime: python3.7
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
      Runtime: python3.7
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
      Runtime: python3.6
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
      Runtime: python3.7
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
Parameteres:
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
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.7
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
        sleep(2)
        result = self.lambda_client.invoke(FunctionName="HelloWorldFunction")
        self.assertEqual(result.get("StatusCode"), 200)

        response = json.loads(result.get("Payload").read().decode("utf-8"))
        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(json.loads(response.get("body")), {"hello": "world2"})


class TestWatchingTemplateChangesDockerFileLocationChanged(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameteres:
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
Parameteres:
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
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.7
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
      Runtime: python3.6
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
Parameteres:
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
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.7
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
      Runtime: python3.6
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
      Runtime: python3.7
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
      Runtime: python3.7
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
      Runtime: python3.6
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
      Runtime: python3.7
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
      Runtime: python3.7
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
      Runtime: python3.6
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
      Runtime: python3.7
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
Parameteres:
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
Parameteres:
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
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.7
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
        "amazon/aws-sam-cli-emulation-image-python3.6",
        "HelloWorldServerlessFunction=public.ecr.aws/sam/emulation-python3.6",
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
