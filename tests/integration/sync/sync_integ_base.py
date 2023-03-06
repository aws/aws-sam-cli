import os

import logging
import json
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Callable

import boto3
import requests
from botocore.exceptions import ClientError
from botocore.config import Config

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.testing_utils import get_sam_command

RETRY_ATTEMPTS = 20
RETRY_WAIT = 1
ZIP_FILE = "layer_zip.zip"

LOG = logging.getLogger(__name__)


class SyncIntegBase(BuildIntegBase, PackageIntegBase):
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
        self.s3_prefix = uuid.uuid4().hex
        self.dependency_layer = True if self.dependency_layer is None else self.dependency_layer
        super().setUp()

    def tearDown(self):
        shutil.rmtree(os.path.join(os.getcwd(), ".aws-sam"), ignore_errors=True)
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

    def _get_stacks(self, stack_name):
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

    def _get_lambda_response(self, lambda_function):
        count = 0
        while count < RETRY_ATTEMPTS:
            try:
                time.sleep(RETRY_WAIT)
                lambda_response = self.lambda_client.invoke(
                    FunctionName=lambda_function, InvocationType="RequestResponse"
                )
                lambda_response_payload = lambda_response.get("Payload").read().decode("utf-8")
                LOG.info("Lambda Response Payload: %s", lambda_response_payload)
                payload = json.loads(lambda_response_payload)
                return payload.get("body")
            except Exception:
                if count == RETRY_ATTEMPTS:
                    raise
            count += 1
        return ""

    def _confirm_lambda_response(self, lambda_function: str, verification_function: Callable) -> None:
        count = 0
        while count < RETRY_ATTEMPTS:
            try:
                time.sleep(RETRY_WAIT)
                lambda_response = self.lambda_client.invoke(
                    FunctionName=lambda_function, InvocationType="RequestResponse"
                )
                lambda_response_payload = lambda_response.get("Payload").read().decode("utf-8")
                LOG.info("Lambda Response Payload: %s", lambda_response_payload)
                payload = json.loads(lambda_response_payload)
                verification_function(payload)
            except Exception:
                if count == RETRY_ATTEMPTS:
                    raise
            count += 1

    def _confirm_lambda_error(self, lambda_function):
        count = 0
        while count < RETRY_ATTEMPTS:
            try:
                time.sleep(RETRY_WAIT)
                lambda_response = self.lambda_client.invoke(
                    FunctionName=lambda_function, InvocationType="RequestResponse"
                )
                if lambda_response.get("FunctionError"):
                    return
            except Exception:
                if count == RETRY_ATTEMPTS:
                    raise
            count += 1
        return ""

    def _get_api_message(self, rest_api):
        api_resource = self.api_client.get_resources(restApiId=rest_api)
        for item in api_resource.get("items"):
            if "GET" in item.get("resourceMethods", {}):
                resource_id = item.get("id")
                break
        self.api_client.flush_stage_cache(restApiId=rest_api, stageName="prod")

        # RestApi deployment needs a wait time before being responsive
        count = 0
        while count < RETRY_ATTEMPTS:
            try:
                time.sleep(RETRY_WAIT)
                api_response = self.api_client.test_invoke_method(
                    restApiId=rest_api, resourceId=resource_id, httpMethod="GET"
                )
                return api_response.get("body")
            except ClientError as ce:
                if count == RETRY_ATTEMPTS:
                    # This test is unstable, a fixed wait time cannot guarantee a successful invocation
                    if "Invalid Method identifier specified" in ce.response.get("Error", {}).get("Message", ""):
                        LOG.error(
                            "The deployed changes are not callable on the client yet, skipping the RestApi invocation"
                        )
                    raise
            except Exception:
                if count == RETRY_ATTEMPTS:
                    raise
            count += 1
        return ""

    def _get_sfn_response(self, state_machine):
        timestamp = str(int(time.time() * 1000))
        name = f"sam_integ_test_{timestamp}"
        sfn_execution = self.sfn_client.start_execution(stateMachineArn=state_machine, name=name)
        execution_arn = sfn_execution.get("executionArn")
        count = 0
        while count < RETRY_ATTEMPTS:
            time.sleep(RETRY_WAIT)
            execution_detail = self.sfn_client.describe_execution(executionArn=execution_arn)
            if execution_detail.get("status") == "SUCCEEDED":
                return execution_detail.get("output")
            count += 1
        return ""

    @staticmethod
    def update_file(source, destination):
        with open(source, "rb") as source_file:
            with open(destination, "wb") as destination_file:
                destination_file.write(source_file.read())

    @staticmethod
    def _extract_contents_from_layer_zip(dep_dir, zipped_layer):
        with tempfile.TemporaryDirectory() as extract_path:
            zipped_path = Path(extract_path, ZIP_FILE)
            with open(zipped_path, "wb") as file:
                file.write(zipped_layer.content)
            with zipfile.ZipFile(zipped_path) as zip_ref:
                zip_ref.extractall(extract_path)
            return os.listdir(Path(extract_path, dep_dir))

    def get_layer_contents(self, arn, dep_dir):
        layer = self.lambda_client.get_layer_version_by_arn(Arn=arn)
        layer_location = layer.get("Content", {}).get("Location", "")
        zipped_layer = requests.get(layer_location)
        return SyncIntegBase._extract_contents_from_layer_zip(dep_dir, zipped_layer)

    def get_dependency_layer_contents_from_arn(self, stack_resources, dep_dir, version):
        layers = stack_resources["AWS::Lambda::LayerVersion"]
        for layer in layers:
            if "DepLayer" in layer:
                layer_version = layer[:-1] + str(version)
                return self.get_layer_contents(layer_version, dep_dir)
        return None

    def get_sync_command_list(
        self,
        template_file=None,
        code=None,
        watch=None,
        resource_id_list=None,
        resource_list=None,
        dependency_layer=None,
        stack_name=None,
        region=None,
        profile=None,
        parameter_overrides=None,
        base_dir=None,
        image_repository=None,
        image_repositories=None,
        s3_bucket=None,
        s3_prefix=None,
        kms_key_id=None,
        capabilities=None,
        capabilities_list=None,
        role_arn=None,
        notification_arns=None,
        tags=None,
        metadata=None,
        debug=None,
        use_container=False,
        build_in_source=None,
    ):
        command_list = [get_sam_command(), "sync"]

        command_list += ["-t", str(template_file)]
        if code:
            command_list += ["--code"]
        if watch:
            command_list += ["--watch"]
        if resource_id_list:
            for resource_id in resource_id_list:
                command_list += ["--resource-id", str(resource_id)]
        if resource_list:
            for resource in resource_list:
                command_list += ["--resource", str(resource)]
        if dependency_layer:
            command_list += ["--dependency-layer"]
        if not dependency_layer:
            command_list += ["--no-dependency-layer"]
        if stack_name:
            command_list += ["--stack-name", str(stack_name)]
        if region:
            command_list += ["--region", str(region)]
        if profile:
            command_list += ["--profile", str(profile)]
        if parameter_overrides:
            command_list += ["--parameter-overrides", str(parameter_overrides)]
        if base_dir:
            command_list += ["-s", str(base_dir)]
        if image_repository:
            command_list += ["--image-repository", str(image_repository)]
        if image_repositories:
            command_list += ["--image-repositories", str(image_repositories)]
        if s3_bucket:
            command_list += ["--s3-bucket", str(s3_bucket)]
        if s3_prefix:
            command_list += ["--s3-prefix", str(s3_prefix)]
        if kms_key_id:
            command_list += ["--kms-key-id", str(kms_key_id)]
        if capabilities:
            command_list += ["--capabilities", str(capabilities)]
        elif capabilities_list:
            command_list.append("--capabilities")
            for capability in capabilities_list:
                command_list.append(str(capability))
        if role_arn:
            command_list += ["--role-arn", str(role_arn)]
        if notification_arns:
            command_list += ["--notification-arns", str(notification_arns)]
        if tags:
            command_list += ["--tags", str(tags)]
        if metadata:
            command_list += ["--metadata", json.dumps(metadata)]
        if debug:
            command_list += ["--debug"]
        if use_container:
            command_list += ["--use-container"]
        if build_in_source is not None:
            command_list += ["--build-in-source"] if build_in_source else ["--no-build-in-source"]

        return command_list
