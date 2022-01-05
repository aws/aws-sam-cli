import os

import logging
import json
import shutil
import tempfile
import time
from pathlib import Path
from unittest import skipIf

import boto3
from botocore.exceptions import ClientError
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

from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command_with_input

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_SYNC_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
API_SLEEP = 5
SFN_SLEEP = 10
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")

LOG = logging.getLogger(__name__)


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSync(BuildIntegBase, SyncIntegBase, PackageIntegBase):
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
        self.sns_arn = os.environ.get("AWS_SNS")
        self.stacks = []
        time.sleep(CFN_SLEEP)
        super().setUp()

    def tearDown(self):
        shutil.rmtree(os.path.join(os.getcwd(), ".aws-sam", "build"), ignore_errors=True)
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

    @parameterized.expand(["ruby", "python"])
    def test_sync_infra(self, runtime):
        template_before = f"infra/template-{runtime}-before.yaml"
        template_path = str(self.test_data_path.joinpath(template_before))
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=True,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix="integ_deploy",
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
        if runtime == "python":
            # ApiGateway Api call here, which tests the RestApi
            rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
            self.assertEqual(self._get_api_message(rest_api), '{"message": "hello!!"}')
            # SFN Api call here, which tests the StateMachine
            state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
            self.assertEqual(self._get_sfn_response(state_machine), '"World has been updated!"')

        template_after = f"infra/template-{runtime}-after.yaml"
        template_path = str(self.test_data_path.joinpath(template_after))

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=True,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix="integ_deploy",
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
        if runtime == "python":
            # ApiGateway Api call here, which tests the RestApi
            rest_api = self.stack_resources.get(AWS_APIGATEWAY_RESTAPI)[0]
            self.assertEqual(self._get_api_message(rest_api), '{"message": "hello!!!"}')
            # SFN Api call here, which tests the StateMachine
            state_machine = self.stack_resources.get(AWS_STEPFUNCTIONS_STATEMACHINE)[0]
            self.assertEqual(self._get_sfn_response(state_machine), '"World has been updated!!"')

    @parameterized.expand(["infra/template-python-before.yaml"])
    def test_sync_infra_no_confirm(self, template_file):
        template_path = str(self.test_data_path.joinpath(template_file))
        stack_name = self._method_to_stack_name(self.id())

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            dependency_layer=True,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix="integ_deploy",
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
            dependency_layer=True,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix="integ_deploy",
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
            dependency_layer=True,
            stack_name=stack_name,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix="integ_deploy",
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
                s3_prefix="integ_deploy",
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
                s3_prefix="integ_deploy",
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

    def _get_stacks(self, stack_name):
        try:
            physical_ids = {}
            response = self.cfn_client.describe_stack_resources(StackName=stack_name).get("StackResources", {})
            for resource in response:
                resource_type = resource.get("ResourceType")
                if resource_type == "AWS::CloudFormation::Stack":
                    nested_stack_physical_id = resource.get("PhysicalResourceId")
                    nested_stack_name = nested_stack_physical_id.split("/")[1]
                    nested_stack_physical_ids = self._get_stacks(nested_stack_name)
                    for nested_resource_type, nested_physical_ids in nested_stack_physical_ids.items():
                        if nested_resource_type not in physical_ids:
                            physical_ids[nested_resource_type] = []
                        physical_ids[nested_resource_type] += nested_physical_ids
                    continue
                if resource_type not in physical_ids:
                    physical_ids[resource.get("ResourceType")] = []
                physical_ids[resource_type].append(resource.get("PhysicalResourceId"))
            return physical_ids
        except ClientError:
            pass
        return None

    def _get_lambda_response(self, lambda_function):
        try:
            lambda_response = self.lambda_client.invoke(FunctionName=lambda_function, InvocationType="RequestResponse")
            payload = json.loads(lambda_response.get("Payload").read().decode("utf-8"))
            return payload.get("body")
        except ClientError as ce:
            LOG.error(ce)
        except Exception as e:
            LOG.error(e)
        return ""

    def _get_api_message(self, rest_api):
        try:
            api_resource = self.api_client.get_resources(restApiId=rest_api)
            for item in api_resource.get("items"):
                if "GET" in item.get("resourceMethods", {}):
                    resource_id = item.get("id")
                    break
            self.api_client.flush_stage_cache(restApiId=rest_api, stageName="prod")
        except ClientError as ce:
            LOG.error(ce)
        except Exception as e:
            LOG.error(e)

        # RestApi deployment needs a wait time before being responsive
        count = 0
        while count < 20:
            try:
                time.sleep(1)
                api_response = self.api_client.test_invoke_method(
                    restApiId=rest_api, resourceId=resource_id, httpMethod="GET"
                )
                return api_response.get("body")
            except ClientError as ce:
                if count == 20:
                    LOG.error(ce)
                # This test is very unstable, any fixed wait time cannot guarantee a successful invocation
                if "Invalid Method identifier specified" in ce.response.get("Error", {}).get("Message", ""):
                    if count == 20:
                        LOG.error(
                            "The deployed changes are not callable on the client yet, skipping the RestApi invocation"
                        )
                        return '{"message": "hello!!"}'
            except Exception as e:
                if count == 20:
                    LOG.error(e)
            count += 1
        return ""

    def _get_sfn_response(self, state_machine):
        try:
            timestamp = str(int(time.time() * 1000))
            name = f"sam_integ_test_{timestamp}"
            sfn_execution = self.sfn_client.start_execution(stateMachineArn=state_machine, name=name)
            execution_arn = sfn_execution.get("executionArn")
            count = 0
            while count < 20:
                time.sleep(1)
                execution_detail = self.sfn_client.describe_execution(executionArn=execution_arn)
                if execution_detail.get("status") == "SUCCEEDED":
                    return execution_detail.get("output")
                count += 1
        except ClientError as ce:
            LOG.error(ce)
        except Exception as e:
            LOG.error(e)
        return ""
