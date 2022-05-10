import os
import platform

import logging
import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from unittest import skipIf

import pytest
import boto3

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
LAMBDA_SLEEP = 3
API_SLEEP = 5
SFN_SLEEP = 5
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")

LOG = logging.getLogger(__name__)


class TestSyncCodeBase(SyncIntegBase):
    temp_dir = ""
    stack_name = ""
    template_path = ""
    template = ""

    @pytest.fixture(autouse=True, scope="class")
    def sync_code_base(self):
        with tempfile.TemporaryDirectory() as temp:
            TestSyncCode.temp_dir = Path(temp).joinpath("code")
            shutil.copytree(self.test_data_path.joinpath("code").joinpath("before"), TestSyncCode.temp_dir)

            TestSyncCode.template_path = TestSyncCode.temp_dir.joinpath(self.template)
            TestSyncCode.stack_name = self._method_to_stack_name(self.id())

            # Run infra sync
            sync_command_list = self.get_sync_command_list(
                template_file=TestSyncCode.template_path,
                code=False,
                watch=False,
                base_dir=TestSyncCode.temp_dir,
                dependency_layer=True,
                stack_name=TestSyncCode.stack_name,
                parameter_overrides="Parameter=Clarity",
                image_repository=self.ecr_repo_name,
                s3_prefix=uuid.uuid4().hex,
                kms_key_id=self.kms_key,
                tags="integ=true clarity=yes foo_bar=baz",
            )

            sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
            self.assertEqual(sync_process_execute.process.returncode, 0)
            self.assertIn("Stack creation succeeded. Sync infra completed.", str(sync_process_execute.stderr))

            yield

            shutil.rmtree(os.path.join(os.getcwd(), ".aws-sam", "build"), ignore_errors=True)
            cfn_client = boto3.client("cloudformation")
            ecr_client = boto3.client("ecr")
            self._delete_companion_stack(
                cfn_client, ecr_client, self._stack_name_to_companion_stack(TestSyncCode.stack_name)
            )
            cfn_client.delete_stack(StackName=TestSyncCode.stack_name)


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncCode(TestSyncCodeBase):
    template = "template-python.yaml"

    def test_sync_code_function(self):
        shutil.rmtree(TestSyncCode.temp_dir.joinpath("function"), ignore_errors=True)
        shutil.copytree(
            self.test_data_path.joinpath("code").joinpath("after").joinpath("function"),
            TestSyncCode.temp_dir.joinpath("function"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCode.template_path,
            code=True,
            watch=False,
            resource="AWS::Serverless::Function",
            dependency_layer=True,
            stack_name=TestSyncCode.stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCode.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "8")

    def test_sync_code_layer(self):
        shutil.rmtree(TestSyncCode.temp_dir.joinpath("layer"), ignore_errors=True)
        shutil.copytree(
            self.test_data_path.joinpath("code").joinpath("after").joinpath("layer"),
            TestSyncCode.temp_dir.joinpath("layer"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCode.template_path,
            code=True,
            watch=False,
            resource="AWS::Serverless::LayerVersion",
            dependency_layer=True,
            stack_name=TestSyncCode.stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCode.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunction":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "9")

    def test_sync_code_rest_api(self):
        shutil.rmtree(TestSyncCode.temp_dir.joinpath("apigateway"), ignore_errors=True)
        shutil.copytree(
            self.test_data_path.joinpath("code").joinpath("after").joinpath("apigateway"),
            TestSyncCode.temp_dir.joinpath("apigateway"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCode.template_path,
            code=True,
            watch=False,
            base_dir=TestSyncCode.temp_dir,
            resource="AWS::Serverless::Api",
            stack_name=TestSyncCode.stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)

        time.sleep(API_SLEEP)
        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCode.stack_name)
        # ApiGateway Api call here, which tests the RestApi
        rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 2"}')

    def test_sync_code_state_machine(self):
        shutil.rmtree(TestSyncCode.temp_dir.joinpath("statemachine"), ignore_errors=True)
        shutil.copytree(
            self.test_data_path.joinpath("code").joinpath("after").joinpath("statemachine"),
            TestSyncCode.temp_dir.joinpath("statemachine"),
        )
        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCode.template_path,
            code=True,
            watch=False,
            base_dir=TestSyncCode.temp_dir,
            resource="AWS::Serverless::StateMachine",
            stack_name=TestSyncCode.stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCode.stack_name)
        # SFN Api call here, which tests the StateMachine
        time.sleep(SFN_SLEEP)
        state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        self.assertEqual(self._get_sfn_response(state_machine), '"World 2"')


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncCodeDotnetFunctionTemplate(TestSyncCodeBase):
    template = "template-dotnet.yaml"

    def test_sync_code_shared_codeuri(self):
        shutil.rmtree(Path(TestSyncCode.temp_dir).joinpath("dotnet_function"), ignore_errors=True)
        shutil.copytree(
            self.test_data_path.joinpath("code").joinpath("after").joinpath("dotnet_function"),
            Path(TestSyncCode.temp_dir).joinpath("dotnet_function"),
        )

        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCode.template_path,
            code=True,
            watch=False,
            resource="AWS::Serverless::Function",
            dependency_layer=True,
            stack_name=TestSyncCode.stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(TestSyncCode.stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            if lambda_function == "HelloWorldFunctionDotNet":
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "hello sam accelerate!!")
