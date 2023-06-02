import os
import platform

import logging
import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict
from unittest import skipIf

import pytest
import boto3
from parameterized import parameterized_class, parameterized

from samcli.lib.utils.resources import (
    AWS_APIGATEWAY_RESTAPI,
    AWS_LAMBDA_FUNCTION,
    AWS_STEPFUNCTIONS_STATEMACHINE,
)
from tests.integration.sync.sync_integ_base import SyncIntegBase

from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command_with_input

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_SYNC_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
IS_WINDOWS = platform.system().lower() == "windows"
# Some wait time for code updates to be reflected on each service
API_SLEEP = 5
SFN_SLEEP = 5
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")

LOG = logging.getLogger(__name__)


class TestSyncCodeBase(SyncIntegBase):
    stack_name = ""
    template_path = ""
    template = ""
    folder = ""
    parameter_overrides: Dict[str, str] = {}

    @pytest.fixture(scope="class")
    def execute_infra_sync(self):
        TestSyncCodeBase.template_path = self.test_data_path.joinpath(self.folder, "before", self.template)
        TestSyncCodeBase.stack_name = self._method_to_stack_name(self.id())

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=False,
            watch=False,
            dependency_layer=self.dependency_layer,
            stack_name=TestSyncCodeBase.stack_name,
            parameter_overrides=self.parameter_overrides,
            image_repository=self.ecr_repo_name,
            s3_prefix=uuid.uuid4().hex,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )

        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)

        yield sync_process_execute

        cfn_client = boto3.client("cloudformation")
        ecr_client = boto3.client("ecr")
        self._delete_companion_stack(
            cfn_client, ecr_client, self._stack_name_to_companion_stack(TestSyncCodeBase.stack_name)
        )

        cfn_client = boto3.client("cloudformation")
        cfn_client.delete_stack(StackName=TestSyncCodeBase.stack_name)

    @pytest.fixture(autouse=True, scope="class")
    def sync_code_base(self, execute_infra_sync):
        sync_process_execute = execute_infra_sync
        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertIn("Stack creation succeeded. Sync infra completed.", str(sync_process_execute.stderr))


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
@parameterized_class(
    [
        {"dependency_layer": True, "use_container": True},
        {"dependency_layer": True, "use_container": False},
        {"dependency_layer": False, "use_container": False},
        {"dependency_layer": False, "use_container": True},
    ]
)
class TestSyncCode(TestSyncCodeBase):
    template = "template-python.yaml"
    folder = "code"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.parameter_overrides["HelloWorldLayerName"] = f"HelloWorldLayer-{uuid.uuid4().hex}"[:140]

    def test_sync_code_function(self):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "function"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "function"),
            self.test_data_path.joinpath(self.folder, "before", "function"),
        )

        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        if self.dependency_layer and not self.use_container:
            # Test update manifest
            layer_contents = self.get_dependency_layer_contents_from_arn(self.stack_resources, "python", 1)
            self.assertNotIn("requests", layer_contents)

        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::Function"],
            dependency_layer=self.dependency_layer,
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            use_container=self.use_container,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "8")

        if self.dependency_layer and not self.use_container:
            layer_contents = self.get_dependency_layer_contents_from_arn(self.stack_resources, "python", 2)
            self.assertIn("requests", layer_contents)

    def test_sync_code_layer(self):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "layer"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "layer"),
            self.test_data_path.joinpath(self.folder, "before", "layer"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::LayerVersion"],
            dependency_layer=self.dependency_layer,
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            use_container=self.use_container,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "9")

    @pytest.mark.flaky(reruns=3)
    def test_sync_function_layer_race_condition(self):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "function"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "function"),
            self.test_data_path.joinpath(self.folder, "before", "function"),
        )
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "layer"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "layer"),
            self.test_data_path.joinpath(self.folder, "before", "layer"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            dependency_layer=self.dependency_layer,
            resource_list=["AWS::Serverless::LayerVersion", "AWS::Serverless::Function"],
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "7")

    def test_sync_code_rest_api(self):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "apigateway"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "apigateway"),
            self.test_data_path.joinpath(self.folder, "before", "apigateway"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::Api"],
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        time.sleep(API_SLEEP)
        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # ApiGateway Api call here, which tests the RestApi
        rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 2"}')

    def test_sync_code_state_machine(self):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "statemachine"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "statemachine"),
            self.test_data_path.joinpath(self.folder, "before", "statemachine"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::StateMachine"],
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # SFN Api call here, which tests the StateMachine
        time.sleep(SFN_SLEEP)
        state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        self.assertEqual(self._get_sfn_response(state_machine), '"World 2"')


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncCodeDotnetFunctionTemplate(TestSyncCodeBase):
    template = "template-dotnet.yaml"
    dependency_layer = False
    folder = "code"

    def test_sync_code_shared_codeuri(self):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "dotnet_function"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "dotnet_function"),
            self.test_data_path.joinpath(self.folder, "before", "dotnet_function"),
        )

        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::Function"],
            dependency_layer=True,
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunctionDotNet":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "hello sam accelerate!!")


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
@parameterized_class([{"dependency_layer": True}, {"dependency_layer": False}])
class TestSyncCodeNodejsFunctionTemplate(TestSyncCodeBase):
    template = "template-nodejs.yaml"
    folder = "code"

    def test_sync_code_nodejs_function(self):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "nodejs_function"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "nodejs_function"),
            self.test_data_path.joinpath(self.folder, "before", "nodejs_function"),
        )

        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        if self.dependency_layer:
            # Test update manifest
            layer_contents = self.get_dependency_layer_contents_from_arn(
                self.stack_resources, str(Path("nodejs", "node_modules")), 1
            )
            self.assertNotIn("@faker-js", layer_contents)

        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::Function"],
            dependency_layer=self.dependency_layer,
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "Hello world!")

        if self.dependency_layer:
            layer_contents = self.get_dependency_layer_contents_from_arn(
                self.stack_resources, str(Path("nodejs", "node_modules")), 2
            )
            self.assertIn("@faker-js", layer_contents)


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
@parameterized_class([{"dependency_layer": True}, {"dependency_layer": False}])
class TestSyncCodeNested(TestSyncCodeBase):
    template = "template.yaml"
    folder = "nested"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.parameter_overrides = {
            "HelloWorldLayerName": f"HelloWorldLayer-{uuid.uuid4().hex}"[:140],
            "ChildStackHelloWorldLayerName": f"HelloWorldLayer-{uuid.uuid4().hex}"[:140],
        }

    def test_sync_code_nested_function(self):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "child_stack", "child_functions"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "child_stack", "child_functions"),
            self.test_data_path.joinpath(self.folder, "before", "child_stack", "child_functions"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::Function"],
            dependency_layer=self.dependency_layer,
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "ChildStack/ChildChildStack/HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "11")

    def test_sync_code_nested_layer(self):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "root_layer"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "root_layer"),
            self.test_data_path.joinpath(self.folder, "before", "root_layer"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::LayerVersion"],
            dependency_layer=self.dependency_layer,
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "ChildStack/ChildChildStack/HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "12")

    @pytest.mark.flaky(reruns=3)
    def test_sync_nested_function_layer_race_condition(self):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "child_stack", "child_functions"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "child_stack", "child_functions"),
            self.test_data_path.joinpath(self.folder, "before", "child_stack", "child_functions"),
        )
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "root_layer"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "root_layer"),
            self.test_data_path.joinpath(self.folder, "before", "root_layer"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            dependency_layer=self.dependency_layer,
            stack_name=TestSyncCodeBase.stack_name,
            resource_list=["AWS::Serverless::LayerVersion", "AWS::Serverless::Function"],
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "ChildStack/ChildChildStack/HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "10")

    def test_sync_code_nested_rest_api(self):
        shutil.rmtree(
            self.test_data_path.joinpath(self.folder, "before", "child_stack", "child_child_stack", "apigateway")
        )
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "child_stack", "child_child_stack", "apigateway"),
            self.test_data_path.joinpath(self.folder, "before", "child_stack", "child_child_stack", "apigateway"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            dependency_layer=self.dependency_layer,
            resource_list=["AWS::Serverless::Api"],
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        time.sleep(API_SLEEP)
        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # ApiGateway Api call here, which tests the RestApi
        rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 2"}')

    def test_sync_code_nested_state_machine(self):
        shutil.rmtree(
            self.test_data_path.joinpath(self.folder, "before", "child_stack", "child_child_stack", "statemachine"),
        )
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "child_stack", "child_child_stack", "statemachine"),
            self.test_data_path.joinpath(self.folder, "before", "child_stack", "child_child_stack", "statemachine"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::StateMachine"],
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # SFN Api call here, which tests the StateMachine
        time.sleep(SFN_SLEEP)
        state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        self.assertEqual(self._get_sfn_response(state_machine), '"World 2"')


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
@parameterized_class([{"dependency_layer": True}, {"dependency_layer": False}])
class TestSyncCodeNestedWithIntrinsics(TestSyncCodeBase):
    template = "template.yaml"
    folder = "nested_intrinsics"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.parameter_overrides = {
            "ChildStackHelloWorldLayerName": f"ChildStackHelloWorldLayerName-{uuid.uuid4().hex}"[:140]
        }

    def test_sync_code_nested_getattr_layer(self):
        shutil.rmtree(
            self.test_data_path.joinpath(self.folder, "before", "child_stack", "child_layer", "layer"),
        )
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "child_stack", "child_layer", "layer"),
            self.test_data_path.joinpath(self.folder, "before", "child_stack", "child_layer", "layer"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::LayerVersion"],
            dependency_layer=self.dependency_layer,
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "ChildStack/FunctionStack/HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "9")


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncCodeEsbuildFunctionTemplate(TestSyncCodeBase):
    template = "template-esbuild.yaml"
    folder = "code"
    dependency_layer = False

    def test_sync_code_esbuild_function(self):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", "esbuild_function"))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", "esbuild_function"),
            self.test_data_path.joinpath(self.folder, "before", "esbuild_function"),
        )

        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)

        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::Function"],
            dependency_layer=self.dependency_layer,
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)

        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # Lambda Api call here, which tests both the function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "Hello world!")


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
@parameterized_class(
    [
        {"dependency_layer": True, "use_container": True},
        {"dependency_layer": True, "use_container": False},
        {"dependency_layer": False, "use_container": False},
        {"dependency_layer": False, "use_container": True},
    ]
)
class TestSyncLayerCode(TestSyncCodeBase):
    template = "template-python-code-only-layer.yaml"
    folder = "code"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.parameter_overrides = {
            "HelloWorldLayerName": f"HelloWorldLayer-{uuid.uuid4().hex}"[:140],
            "HelloWorldLayerWithoutBuildMethodName": f"HelloWorldLayerWithoutBuildMethod-{uuid.uuid4().hex}"[:140],
            "HelloWorldPreBuiltZipLayerName": f"HelloWorldPreBuiltZipLayer-{uuid.uuid4().hex}"[:140],
        }

    @parameterized.expand(
        [
            ("layer", "HelloWorldLayer", "HelloWorldFunction", "7"),
            (
                "layer_without_build_method",
                "HelloWorldLayerWithoutBuildMethod",
                "HelloWorldFunctionWithLayerWithoutBuild",
                "30",
            ),
            ("layer_zip", "HelloWorldPreBuiltZipLayer", "HelloWorldFunctionWithPreBuiltLayer", "50"),
        ]
    )
    def test_sync_code_layer(self, layer_path, layer_logical_id, function_logical_id, expected_value):
        shutil.rmtree(self.test_data_path.joinpath(self.folder, "before", layer_path))
        shutil.copytree(
            self.test_data_path.joinpath(self.folder, "after", layer_path),
            self.test_data_path.joinpath(self.folder, "before", layer_path),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_id_list=[layer_logical_id],
            dependency_layer=self.dependency_layer,
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            use_container=self.use_container,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == function_logical_id:
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message_from_layer"), expected_value)


class TestFunctionWithPreZippedCodeUri(TestSyncCodeBase):
    template = "template-pre-zipped.yaml"
    folder = "code"
    dependency_layer = False

    def test_pre_zipped_function(self):
        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)

        # first verify current state of the function
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "hello world")

        # update function code with new values
        self.update_file(
            self.test_data_path.joinpath(self.folder, "after", "pre_zipped_function", "app.zip"),
            self.test_data_path.joinpath(self.folder, "before", "pre_zipped_function", "app.zip"),
        )

        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::Function"],
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # Verify changed lambda response
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "hello mars")


class TestFunctionWithSkipBuild(TestSyncCodeBase):
    template = "template-skip-build.yaml"
    folder = "code"
    dependency_layer = False

    def test_skip_build(self):
        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)

        # first verify current state of the function
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "hello world")

        # update function code with new values
        self.update_file(
            self.test_data_path.joinpath(self.folder, "after", "python_function_no_deps", "app_without_numpy.py"),
            self.test_data_path.joinpath(self.folder, "before", "python_function_no_deps", "app.py"),
        )

        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            code=True,
            watch=False,
            resource_list=["AWS::Serverless::Function"],
            stack_name=TestSyncCodeBase.stack_name,
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode(), cwd=self.test_data_path)
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # Verify changed lambda response
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "hello mars")
