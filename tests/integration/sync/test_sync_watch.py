import os
import shutil
import time
import uuid

import logging
import json
import tempfile
from pathlib import Path
from unittest import skipIf

import boto3
from botocore.config import Config
from parameterized import parameterized

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from samcli.lib.utils.resources import (
    AWS_APIGATEWAY_RESTAPI,
    AWS_LAMBDA_FUNCTION,
    AWS_STEPFUNCTIONS_STATEMACHINE,
)
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.integration.sync.sync_integ_base import SyncIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.integration.sync.test_sync_code import API_SLEEP, SFN_SLEEP

from tests.testing_utils import (
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    kill_process,
    read_until_string,
    start_persistent_process,
)
from tests.testing_utils import run_command_with_input

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_SYNC_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")

LOG = logging.getLogger(__name__)

LOG.handlers = []  # This is the key thing for the question!

# Start defining and assigning your handlers here
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
LOG.addHandler(handler)


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncWatch(SyncIntegBase):
    @classmethod
    def setUpClass(cls):
        PackageIntegBase.setUpClass()
        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "sync")

    def setUp(self):
        self.cfn_client = boto3.client("cloudformation")
        self.ecr_client = boto3.client("ecr")
        self.lambda_client = boto3.client("lambda")
        self.api_client = boto3.client("apigateway")
        self.sfn_client = boto3.client("stepfunctions")
        self.stacks = []
        self.s3_prefix = uuid.uuid4().hex
        self.test_dir = Path(tempfile.mkdtemp())
        # Remove temp dir so that shutil.copytree will not throw an error
        # Needed for python 3.6 and 3.7 as these versions don't have dirs_exist_ok
        shutil.rmtree(self.test_dir)
        shutil.copytree(self.test_data_path, self.test_dir)
        super().setUp()

    def tearDown(self):
        kill_process(self.watch_process)
        shutil.rmtree(self.test_dir)
        for stack in self.stacks:
            # because of the termination protection, do not delete aws-sam-cli-managed-default stack
            stack_name = stack["name"]
            if stack_name != SAM_CLI_STACK_NAME:
                region = stack.get("region")
                cfn_client = (
                    self.cfn_client if not region else boto3.client("cloudformation", config=Config(region_name=region))
                )
                ecr_client = self.ecr_client if not region else boto3.client("ecr", config=Config(region_name=region))
                self._delete_companion_stack(cfn_client, ecr_client, self._stack_name_to_companion_stack(stack_name))
                cfn_client.delete_stack(StackName=stack_name)
        super().tearDown()

    @parameterized.expand(["python"])
    def test_sync_watch_infra(self, runtime):
        template_before = f"infra/template-{runtime}-before.yaml"
        template_path = self.test_dir.joinpath(template_before)
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Start watch
        sync_command_list = self.get_sync_command_list(
            template_file=str(template_path),
            code=False,
            watch=True,
            dependency_layer=True,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        self.watch_process = start_persistent_process(sync_command_list, cwd=self.test_dir)
        read_until_string(self.watch_process, "Enter Y to proceed with the command, or enter N to cancel:\n")

        self.watch_process.stdin.write("y\n")

        read_until_string(self.watch_process, "\x1b[32mInfra sync completed.\x1b[0m\n", timeout=600)

        # Initial Infra Validation
        self.stack_resources = self._get_stacks(stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "7")
        rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 1"}')
        state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        self.assertEqual(self._get_sfn_response(state_machine), '"World 1"')

        self.update_file(
            self.test_dir.joinpath(f"infra/template-{runtime}-after.yaml"),
            self.test_dir.joinpath(f"infra/template-{runtime}-before.yaml"),
        )

        read_until_string(self.watch_process, "\x1b[32mInfra sync completed.\x1b[0m\n", timeout=600)

        # Updated Infra Validation
        self.stack_resources = self._get_stacks(stack_name)

        # Lambda
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "9")

        # APIGW
        rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 2"}')

        # SFN
        state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        self.assertEqual(self._get_sfn_response(state_machine), '"World 2"')

    def test_sync_watch_code(self):
        template_before = f"code/before/template-python.yaml"
        template_path = self.test_dir.joinpath(template_before)
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Start watch
        sync_command_list = self.get_sync_command_list(
            template_file=str(template_path),
            code=False,
            watch=True,
            dependency_layer=True,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        self.watch_process = start_persistent_process(sync_command_list, cwd=self.test_dir)
        read_until_string(self.watch_process, "Enter Y to proceed with the command, or enter N to cancel:\n")

        self.watch_process.stdin.write("y\n")

        read_until_string(self.watch_process, "\x1b[32mInfra sync completed.\x1b[0m\n", timeout=600)

        # Initial Infra Validation
        self.stack_resources = self._get_stacks(stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "7")
        rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 1"}')
        state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        self.assertEqual(self._get_sfn_response(state_machine), '"World 1"')

        self.stack_resources = self._get_stacks(stack_name)

        # Test Lambda Function
        self.update_file(
            self.test_dir.joinpath("code/after/function/app.py"),
            self.test_dir.joinpath("code/before/function/app.py"),
        )
        read_until_string(
            self.watch_process, "\x1b[32mFinished syncing Lambda Function HelloWorldFunction.\x1b[0m\n", timeout=30
        )
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "8")

        # Test Lambda Layer
        self.update_file(
            self.test_dir.joinpath("code/after/layer/layer_method.py"),
            self.test_dir.joinpath("code/before/layer/layer_method.py"),
        )
        read_until_string(
            self.watch_process,
            "\x1b[32mFinished syncing Function Layer Reference Sync HelloWorldFunction.\x1b[0m\n",
            timeout=30,
        )
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "9")

        # Test APIGW
        self.update_file(
            self.test_dir.joinpath("code/after/apigateway/definition.json"),
            self.test_dir.joinpath("code/before/apigateway/definition.json"),
        )
        read_until_string(self.watch_process, "\x1b[32mFinished syncing RestApi HelloWorldApi.\x1b[0m\n", timeout=20)
        time.sleep(API_SLEEP)
        rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 2"}')

        # Test SFN
        self.update_file(
            self.test_dir.joinpath("code/after/statemachine/function.asl.json"),
            self.test_dir.joinpath("code/before/statemachine/function.asl.json"),
        )
        read_until_string(
            self.watch_process, "\x1b[32mFinished syncing StepFunctions HelloStepFunction.\x1b[0m\n", timeout=20
        )
        state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        time.sleep(SFN_SLEEP)
        self.assertEqual(self._get_sfn_response(state_machine), '"World 2"')

    def update_file(self, source, destination):
        with open(source, "rb") as source_file:
            with open(destination, "wb") as destination_file:
                destination_file.write(source_file.read())
