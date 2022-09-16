import os
import platform

import logging
import json
import shutil
import tempfile
from pathlib import Path
from unittest import skipIf

import pytest
from parameterized import parameterized, parameterized_class

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


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
@parameterized_class([{"dependency_layer": True}, {"dependency_layer": False}])
class TestSyncInfra(SyncIntegBase):
    @skipIf(
        IS_WINDOWS,
        "Skip sync ruby tests in windows",
    )
    @pytest.mark.flaky(reruns=3)
    @parameterized.expand([["ruby", False], ["python", False], ["python", True]])
    def test_sync_infra(self, runtime, use_container):
        template_before = f"infra/template-{runtime}-before.yaml"
        template_path = str(self.test_data_path.joinpath(template_before))
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=self.dependency_layer,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            use_container=use_container,
        )

        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertIn("Stack creation succeeded. Sync infra completed.", str(sync_process_execute.stderr))

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "7")
        if runtime == "python":
            # ApiGateway Api call here, which tests the RestApi
            rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
            self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 1"}')
            # SFN Api call here, which tests the StateMachine
            state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
            self.assertEqual(self._get_sfn_response(state_machine), '"World 1"')

        template_after = f"infra/template-{runtime}-after.yaml"
        template_path = str(self.test_data_path.joinpath(template_after))

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=self.dependency_layer,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            use_container=use_container,
        )

        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertIn("Stack update succeeded. Sync infra completed.", str(sync_process_execute.stderr))
        self.assertNotIn("Commands you can use next", str(sync_process_execute.stderr))

        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(stack_name)
        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "9")
        if runtime == "python":
            # ApiGateway Api call here, which tests the RestApi
            rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
            self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 2"}')
            # SFN Api call here, which tests the StateMachine
            state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
            self.assertEqual(self._get_sfn_response(state_machine), '"World 2"')

    @parameterized.expand(["infra/template-python-before.yaml"])
    def test_sync_infra_no_confirm(self, template_file):
        template_path = str(self.test_data_path.joinpath(template_file))
        stack_name = self._method_to_stack_name(self.id())

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=self.dependency_layer,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "n\n".encode())

        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertNotIn("Build Succeeded", str(sync_process_execute.stderr))

    @parameterized.expand(["infra/template-python-before.yaml"])
    def test_sync_infra_no_stack_name(self, template_file):
        template_path = str(self.test_data_path.joinpath(template_file))

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=self.dependency_layer,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
        )

        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 2)
        self.assertIn("Error: Missing option '--stack-name'.", str(sync_process_execute.stderr))

    @parameterized.expand(["infra/template-python-before.yaml"])
    def test_sync_infra_no_capabilities(self, template_file):
        template_path = str(self.test_data_path.joinpath(template_file))
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=self.dependency_layer,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            capabilities="CAPABILITY_IAM",
            tags="integ=true clarity=yes foo_bar=baz",
        )

        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 1)
        self.assertIn(
            "An error occurred (InsufficientCapabilitiesException) when calling the CreateStack operation: \
Requires capabilities : [CAPABILITY_AUTO_EXPAND]",
            str(sync_process_execute.stderr),
        )

    @parameterized.expand(["infra/template-python-before.yaml"])
    def test_sync_infra_s3_bucket_option(self, template_file):
        template_path = str(self.test_data_path.joinpath(template_file))
        stack_name = self._method_to_stack_name(self.id())

        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=self.dependency_layer,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_bucket=self.bucket_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            tags="integ=true clarity=yes foo_bar=baz",
        )

        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertIn("Stack creation succeeded. Sync infra completed.", str(sync_process_execute.stderr))

        # Make sure all resources are created properly after specifying custom bucket
        # CFN Api call here to collect all the stack resources
        self.stack_resources = self._get_stacks(stack_name)

        # Lambda Api call here, which tests both the python function and the layer
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("extra_message", lambda_response)
            self.assertEqual(lambda_response.get("message"), "7")

        # ApiGateway Api call here, which tests both of the RestApi
        rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
        self.assertEqual(self._get_api_message(rest_api), '{"message": "hello 1"}')

        # SFN Api call here, which tests the StateMachine
        state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
        self.assertEqual(self._get_sfn_response(state_machine), '"World 1"')


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncInfraCDKTemplates(SyncIntegBase):
    dependency_layer = None

    @parameterized.expand(
        [
            (
                "cdk_v1_synthesized_template_zip_functions.json",
                "cdk_v1_synthesized_template_zip_functions_after.json",
                None,
                False,
            ),
            (
                "cdk_v1_synthesized_template_zip_functions.json",
                "cdk_v1_synthesized_template_zip_functions_after.json",
                None,
                True,
            ),
            (
                "cdk_v1_synthesized_template_Level1_nested_zip_functions.json",
                "cdk_v1_synthesized_template_Level1_nested_zip_functions_after.json",
                None,
                False,
            ),
            (
                "cdk_v1_synthesized_template_image_functions.json",
                "cdk_v1_synthesized_template_image_functions_after.json",
                "ColorsRandomFunctionF61B9209",
                False,
            ),
            (
                "cdk_v1_synthesized_template_image_functions.json",
                "cdk_v1_synthesized_template_image_functions_after.json",
                "ColorsRandomFunction",
                False,
            ),
            (
                "cdk_v1_synthesized_template_Level1_nested_image_functions.json",
                "cdk_v1_synthesized_template_Level1_nested_image_functions_after.json",
                "ColorsRandomFunctionF61B9209",
                False,
            ),
            (
                "cdk_v1_synthesized_template_Level1_nested_image_functions.json",
                "cdk_v1_synthesized_template_Level1_nested_image_functions_after.json",
                "ColorsRandomFunction",
                False,
            ),
            (
                "cdk_v1_synthesized_template_Level1_nested_image_functions.json",
                "cdk_v1_synthesized_template_Level1_nested_image_functions_after.json",
                "Level1Stack/Level2Stack/ColorsRandomFunction",
                False,
            ),
        ]
    )
    def test_cdk_templates(self, template_file, template_after, function_id, dependency_layer):
        repository = ""
        if function_id:
            repository = f"{function_id}={self.ecr_repo_name}"
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            shutil.copytree(str(self.test_data_path.joinpath("infra/cdk")), str(temp_path.joinpath("cdk")))
            template_path = str(temp_path.joinpath("cdk").joinpath(template_file))
            stack_name = self._method_to_stack_name(self.id())
            self.stacks.append({"name": stack_name})

            # Run infra sync
            sync_command_list = self.get_sync_command_list(
                template_file=template_path,
                code=False,
                watch=False,
                dependency_layer=dependency_layer,
                stack_name=stack_name,
                parameter_overrides="Parameter=Clarity",
                image_repositories=repository,
                s3_prefix=self.s3_prefix,
                kms_key_id=self.kms_key,
                tags="integ=true clarity=yes foo_bar=baz",
            )
            sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
            self.assertEqual(sync_process_execute.process.returncode, 0)
            self.assertIn("Stack creation succeeded. Sync infra completed.", str(sync_process_execute.stderr))

            # CFN Api call here to collect all the stack resources
            self.stack_resources = self._get_stacks(stack_name)
            # Lambda Api call here, which tests both the python function and the layer
            lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
            for lambda_function in lambda_functions:
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "7")

            template_path = str(temp_path.joinpath("cdk").joinpath(template_after))

            # Run infra sync
            sync_command_list = self.get_sync_command_list(
                template_file=template_path,
                code=False,
                watch=False,
                dependency_layer=dependency_layer,
                stack_name=stack_name,
                parameter_overrides="Parameter=Clarity",
                image_repositories=repository,
                s3_prefix=self.s3_prefix,
                kms_key_id=self.kms_key,
                tags="integ=true clarity=yes foo_bar=baz",
            )

            sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
            self.assertEqual(sync_process_execute.process.returncode, 0)
            self.assertIn("Stack update succeeded. Sync infra completed.", str(sync_process_execute.stderr))

            # CFN Api call here to collect all the stack resources
            self.stack_resources = self._get_stacks(stack_name)
            # Lambda Api call here, which tests both the python function and the layer
            lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
            for lambda_function in lambda_functions:
                lambda_response = json.loads(self._get_lambda_response(lambda_function))
                self.assertIn("extra_message", lambda_response)
                self.assertEqual(lambda_response.get("message"), "9")


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
@parameterized_class([{"dependency_layer": True}, {"dependency_layer": False}])
class TestSyncInfraWithJava(SyncIntegBase):
    @parameterized.expand(["infra/template-java.yaml"])
    def test_sync_infra_with_java(self, template_file):
        """This will test a case where user will flip ADL flag between sync sessions"""
        template_path = str(self.test_data_path.joinpath(template_file))
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # first run with current dependency layer value
        self._run_sync_and_validate_lambda_call(self.dependency_layer, template_path, stack_name)

        # now flip the dependency layer value and re-run the sync & tests
        self._run_sync_and_validate_lambda_call(not self.dependency_layer, template_path, stack_name)

    def _run_sync_and_validate_lambda_call(self, dependency_layer: bool, template_path: str, stack_name: str) -> None:
        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=dependency_layer,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertIn("Sync infra completed.", str(sync_process_execute.stderr))

        self.stack_resources = self._get_stacks(stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertIn("message", lambda_response)
            self.assertIn("sum", lambda_response)
            self.assertEqual(lambda_response.get("message"), "hello world")
            self.assertEqual(lambda_response.get("sum"), 12)


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSyncInfraWithEsbuild(SyncIntegBase):
    dependency_layer = False

    @parameterized.expand(["code/before/template-esbuild.yaml"])
    def test_sync_infra_esbuild(self, template_file):
        template_path = str(self.test_data_path.joinpath(template_file))
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=self.dependency_layer,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            tags="integ=true clarity=yes foo_bar=baz",
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertIn("Sync infra completed.", str(sync_process_execute.stderr))

        self.stack_resources = self._get_stacks(stack_name)
        lambda_functions = self.stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertEqual(lambda_response.get("message"), "hello world")
