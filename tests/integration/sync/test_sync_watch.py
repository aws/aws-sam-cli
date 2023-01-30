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
from parameterized import parameterized_class

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from samcli.lib.utils.resources import (
    AWS_APIGATEWAY_RESTAPI,
    AWS_LAMBDA_FUNCTION,
    AWS_STEPFUNCTIONS_STATEMACHINE,
)
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
class TestSyncWatchBase(SyncIntegBase):
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
        self.template_before = "" if not self.template_before else self.template_before
        self.stack_name = self._method_to_stack_name(self.id())
        # Remove temp dir so that shutil.copytree will not throw an error
        # Needed for python 3.7 as these versions don't have dirs_exist_ok
        shutil.rmtree(self.test_dir)
        shutil.copytree(self.test_data_path, self.test_dir)
        super().setUp()
        self._setup_verify_infra()

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

    def run_initial_infra_validation(self) -> None:
        """Runs initial infra validation after deployment is completed"""
        self.stack_resources = self._get_stacks(self.stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "7")
        rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 1"}')
        state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        self.assertEqual(self._get_sfn_response(state_machine), '"World 1"')

    def _setup_verify_infra(self):
        template_path = self.test_dir.joinpath(self.template_before)
        self.stacks.append({"name": self.stack_name})

        # Start watch
        sync_command_list = self.get_sync_command_list(
            template_file=str(template_path),
            code=False,
            watch=True,
            dependency_layer=self.dependency_layer,
            stack_name=self.stack_name,
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

        self.run_initial_infra_validation()

    def _verify_infra_changes(self, resources):
        # Lambda
        lambda_functions = resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "9")

        # APIGW
        rest_api = resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 2"}')

        # SFN
        state_machine = resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        self.assertEqual(self._get_sfn_response(state_machine), '"World 2"')


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncWatchEsbuildBase(TestSyncWatchBase):
    @classmethod
    def setUpClass(cls):
        PackageIntegBase.setUpClass()
        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "sync")

    def setUp(self):
        super().setUp()

    def _setup_verify_infra(self):
        template_path = self.test_dir.joinpath(self.template_before)
        self.stacks.append({"name": self.stack_name})

        # Start watch
        sync_command_list = self.get_sync_command_list(
            template_file=str(template_path),
            code=False,
            watch=True,
            dependency_layer=self.dependency_layer,
            stack_name=self.stack_name,
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

        self.stack_resources = self._get_stacks(self.stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertEqual(lambda_response.get("message"), "hello world")


@parameterized_class(
    [{"runtime": "python", "dependency_layer": True}, {"runtime": "python", "dependency_layer": False}]
)
class TestSyncWatchInfra(TestSyncWatchBase):
    @classmethod
    def setUpClass(cls):
        cls.template_before = f"infra/template-{cls.runtime}-before.yaml"
        super(TestSyncWatchInfra, cls).setUpClass()

    def test_sync_watch_infra(self):

        self.update_file(
            self.test_dir.joinpath(f"infra/template-{self.runtime}-after.yaml"),
            self.test_dir.joinpath(f"infra/template-{self.runtime}-before.yaml"),
        )

        read_until_string(self.watch_process, "\x1b[32mInfra sync completed.\x1b[0m\n", timeout=600)

        # Updated Infra Validation
        self.stack_resources = self._get_stacks(self.stack_name)
        self._verify_infra_changes(self.stack_resources)


@parameterized_class([{"dependency_layer": True}, {"dependency_layer": False}])
class TestSyncWatchCode(TestSyncWatchBase):
    template_before = str(Path("code", "before", "template-python.yaml"))

    def test_sync_watch_code(self):
        self.stack_resources = self._get_stacks(self.stack_name)

        if self.dependency_layer:
            # Test update manifest
            layer_contents = self.get_dependency_layer_contents_from_arn(self.stack_resources, "python", 1)
            self.assertNotIn("requests", layer_contents)
            self.update_file(
                self.test_dir.joinpath("code", "after", "function", "requirements.txt"),
                self.test_dir.joinpath("code", "before", "function", "requirements.txt"),
            )
            read_until_string(
                self.watch_process,
                "\x1b[32mFinished syncing Function Layer Reference Sync HelloWorldFunction.\x1b[0m\n",
                timeout=45,
            )
            layer_contents = self.get_dependency_layer_contents_from_arn(self.stack_resources, "python", 2)
            self.assertIn("requests", layer_contents)

        # Test Lambda Function
        self.update_file(
            self.test_dir.joinpath("code", "after", "function", "app.py"),
            self.test_dir.joinpath("code", "before", "function", "app.py"),
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
            self.test_dir.joinpath("code", "after", "layer", "layer_method.py"),
            self.test_dir.joinpath("code", "before", "layer", "layer_method.py"),
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
            self.test_dir.joinpath("code", "after", "apigateway", "definition.json"),
            self.test_dir.joinpath("code", "before", "apigateway", "definition.json"),
        )
        read_until_string(self.watch_process, "\x1b[32mFinished syncing RestApi HelloWorldApi.\x1b[0m\n", timeout=20)
        time.sleep(API_SLEEP)
        rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 2"}')

        # Test SFN
        self.update_file(
            self.test_dir.joinpath("code", "after", "statemachine", "function.asl.json"),
            self.test_dir.joinpath("code", "before", "statemachine", "function.asl.json"),
        )
        read_until_string(
            self.watch_process, "\x1b[32mFinished syncing StepFunctions HelloStepFunction.\x1b[0m\n", timeout=20
        )
        state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        time.sleep(SFN_SLEEP)
        self.assertEqual(self._get_sfn_response(state_machine), '"World 2"')


@parameterized_class([{"dependency_layer": True}, {"dependency_layer": False}])
class TestSyncInfraNestedStacks(TestSyncWatchBase):
    template_before = str(Path("infra", "parent-stack.yaml"))

    def test_sync_watch_infra_nested_stack(self):
        self.update_file(
            self.test_dir.joinpath("infra", "template-python-after.yaml"),
            self.test_dir.joinpath("infra", "template-python-before.yaml"),
        )

        read_until_string(self.watch_process, "\x1b[32mInfra sync completed.\x1b[0m\n", timeout=600)

        # Updated Infra Validation
        self.stack_resources = self._get_stacks(self.stack_name)
        self._verify_infra_changes(self.stack_resources)


@parameterized_class([{"dependency_layer": True}, {"dependency_layer": False}])
class TestSyncCodeWatchNestedStacks(TestSyncWatchBase):
    template_before = str(Path("code", "before", "parent-stack.yaml"))

    def test_sync_watch_code_nested_stack(self):
        self.stack_resources = self._get_stacks(self.stack_name)

        if self.dependency_layer:
            # Test update manifest
            layer_contents = self.get_dependency_layer_contents_from_arn(self.stack_resources, "python", 1)
            self.assertNotIn("requests", layer_contents)
            self.update_file(
                self.test_dir.joinpath("code", "after", "function", "requirements.txt"),
                self.test_dir.joinpath("code", "before", "function", "requirements.txt"),
            )
            read_until_string(
                self.watch_process,
                "\x1b[32mFinished syncing Function Layer Reference Sync "
                "LocalNestedChildStack/HelloWorldFunction.\x1b[0m\n",
                timeout=45,
            )
            layer_contents = self.get_dependency_layer_contents_from_arn(self.stack_resources, "python", 2)
            self.assertIn("requests", layer_contents)

        # Test Lambda Function
        self.update_file(
            self.test_dir.joinpath("code", "after", "function", "app.py"),
            self.test_dir.joinpath("code", "before", "function", "app.py"),
        )
        read_until_string(
            self.watch_process,
            "\x1b[32mFinished syncing Lambda Function LocalNestedChildStack/HelloWorldFunction.\x1b[0m\n",
            timeout=30,
        )
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "8")

        # Test Lambda Layer
        self.update_file(
            self.test_dir.joinpath("code", "after", "layer", "layer_method.py"),
            self.test_dir.joinpath("code", "before", "layer", "layer_method.py"),
        )
        read_until_string(
            self.watch_process,
            "\x1b[32mFinished syncing Function Layer Reference Sync LocalNestedChildStack/HelloWorldFunction.\x1b[0m\n",
            timeout=30,
        )
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "9")

        # Test APIGW
        self.update_file(
            self.test_dir.joinpath("code", "after", "apigateway", "definition.json"),
            self.test_dir.joinpath("code", "before", "apigateway", "definition.json"),
        )
        read_until_string(
            self.watch_process,
            "\x1b[32mFinished syncing RestApi LocalNestedChildStack/HelloWorldApi.\x1b[0m\n",
            timeout=20,
        )
        time.sleep(API_SLEEP)
        rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 2"}')

        # Test SFN
        self.update_file(
            self.test_dir.joinpath("code", "after", "statemachine", "function.asl.json"),
            self.test_dir.joinpath("code", "before", "statemachine", "function.asl.json"),
        )
        read_until_string(
            self.watch_process,
            "\x1b[32mFinished syncing StepFunctions LocalNestedChildStack/HelloStepFunction.\x1b[0m\n",
            timeout=20,
        )
        state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        time.sleep(SFN_SLEEP)
        self.assertEqual(self._get_sfn_response(state_machine), '"World 2"')


class TestSyncWatchCodeEsbuild(TestSyncWatchEsbuildBase):
    dependency_layer = False
    template_before = str(Path("code", "before", "template-esbuild.yaml"))

    def test_sync_watch_code(self):
        self.stack_resources = self._get_stacks(self.stack_name)

        # Test Lambda Function
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertNotIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "hello world")

        self.update_file(
            self.test_dir.joinpath("code", "after", "esbuild_function", "app.ts"),
            self.test_dir.joinpath("code", "before", "esbuild_function", "app.ts"),
        )
        read_until_string(
            self.watch_process, "\x1b[32mFinished syncing Lambda Function HelloWorldFunction.\x1b[0m\n", timeout=30
        )
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "Hello world!")


class TestSyncWatchUseContainer(TestSyncWatchBase):
    @classmethod
    def setUpClass(cls):
        super(TestSyncWatchBase, cls).setUpClass()
        cls.use_container = True
        cls.dependency_layer = False

    def _verify_infra_changes(self, resources):
        # Lambda
        lambda_functions = resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "9")


class TestSyncWatchInfraUseContainer(TestSyncWatchUseContainer):
    template_before = f"infra/template-python-before.yaml"

    def test_sync_watch_infra(self):
        self.update_file(
            self.test_dir.joinpath(f"infra/template-python-after.yaml"),
            self.test_dir.joinpath(f"infra/template-python-before.yaml"),
        )

        read_until_string(self.watch_process, "\x1b[32mInfra sync completed.\x1b[0m\n", timeout=600)

        # Updated Infra Validation
        self.stack_resources = self._get_stacks(self.stack_name)
        self._verify_infra_changes(self.stack_resources)


class TestSyncWatchCodeUseContainer(TestSyncWatchUseContainer):
    template_before = str(Path("code", "before", "template-python.yaml"))

    def test_sync_watch_code(self):
        self.stack_resources = self._get_stacks(self.stack_name)

        # Test Lambda Function
        self.update_file(
            self.test_dir.joinpath("code", "after", "function", "requirements.txt"),
            self.test_dir.joinpath("code", "before", "function", "requirements.txt"),
        )
        read_until_string(
            self.watch_process, "\x1b[32mFinished syncing Lambda Function HelloWorldFunction.\x1b[0m\n", timeout=45
        )

        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "7")


@parameterized_class(
    [{"runtime": "python", "dependency_layer": True}, {"runtime": "python", "dependency_layer": False}]
)
class TestSyncWatchCodeOnly(TestSyncWatchBase):
    template_before = str(Path("code", "before", "template-python-code-only.yaml"))

    def run_initial_infra_validation(self) -> None:
        """Runs initial infra validation after deployment is completed"""
        self.stack_resources = self._get_stacks(self.stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "7")

    def test_sync_watch_code(self):
        # first kill previously started sync process
        kill_process(self.watch_process)
        # start new one with code only
        template_path = self.test_dir.joinpath(self.template_before)
        sync_command_list = self.get_sync_command_list(
            template_file=str(template_path),
            code=True,
            watch=True,
            dependency_layer=self.dependency_layer,
            stack_name=self.stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        self.watch_process = start_persistent_process(sync_command_list, cwd=self.test_dir)
        read_until_string(self.watch_process, "\x1b[32mSync watch started.\x1b[0m\n", timeout=30)

        self.stack_resources = self._get_stacks(self.stack_name)

        if self.dependency_layer:
            # Test update manifest
            layer_contents = self.get_dependency_layer_contents_from_arn(self.stack_resources, "python", 1)
            self.assertNotIn("requests", layer_contents)
            self.update_file(
                self.test_dir.joinpath("code", "after", "function", "requirements.txt"),
                self.test_dir.joinpath("code", "before", "function", "requirements.txt"),
            )
            read_until_string(
                self.watch_process,
                "\x1b[32mFinished syncing Function Layer Reference Sync HelloWorldFunction.\x1b[0m\n",
                timeout=45,
            )
            layer_contents = self.get_dependency_layer_contents_from_arn(self.stack_resources, "python", 2)
            self.assertIn("requests", layer_contents)

        # Test Lambda Function
        self.update_file(
            self.test_dir.joinpath("code", "after", "function", "app.py"),
            self.test_dir.joinpath("code", "before", "function", "app.py"),
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
            self.test_dir.joinpath("code", "after", "layer", "layer_method.py"),
            self.test_dir.joinpath("code", "before", "layer", "layer_method.py"),
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

        # updating infra should not trigger an infra sync
        self.update_file(
            self.test_dir.joinpath(f"infra/template-{self.runtime}-after.yaml"),
            self.test_dir.joinpath(f"code/before/template-{self.runtime}-code-only.yaml"),
        )

        read_until_string(
            self.watch_process,
            "\x1b[33mYou have enabled the --code flag, which limits sam sync updates to code changes only. To do a "
            "complete infrastructure and code sync, remove the --code flag.\x1b[0m\n",
            timeout=30,
        )
