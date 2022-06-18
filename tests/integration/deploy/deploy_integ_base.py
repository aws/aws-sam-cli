from unittest import TestCase
from enum import Enum, auto

import boto3
from botocore.config import Config
from tests.testing_utils import get_sam_command


class ResourceType(Enum):
    LAMBDA_FUNCTION = auto()
    S3_BUCKET = auto()
    IAM_ROLE = auto()


class DeployIntegBase(TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        super().setUp()
        self.left_over_resources = {
            ResourceType.LAMBDA_FUNCTION: list(),
            ResourceType.S3_BUCKET: list(),
            ResourceType.IAM_ROLE: list(),
        }

    def tearDown(self):
        super().tearDown()
        self.delete_s3_buckets()
        self.delete_iam_roles()
        self.delete_lambda_functions()

    def delete_s3_buckets(self):
        config = Config(retries={"max_attempts": 10, "mode": "adaptive"})
        s3 = boto3.resource("s3", config=config)

        for bucket_name in self.left_over_resources[ResourceType.S3_BUCKET]:
            try:
                s3_bucket = s3.Bucket(bucket_name)
                s3_bucket.objects.all().delete()
                s3_bucket.object_versions.all().delete()
                s3_bucket.delete()
            except s3.meta.client.exceptions.NoSuchBucket:
                pass

    def delete_iam_roles(self):
        iam = boto3.resource("iam")
        for role_name in self.left_over_resources[ResourceType.IAM_ROLE]:
            try:
                role = iam.Role(role_name)
                policies = role.attached_policies.all()
                for policy in policies:
                    role.detach_policy(PolicyArn=policy.arn)
                role.delete()
            except iam.meta.client.exceptions.NoSuchEntityException:
                pass

    def delete_lambda_functions(self):
        lambda_client = boto3.client("lambda")
        for function_name in self.left_over_resources[ResourceType.LAMBDA_FUNCTION]:
            try:
                lambda_client.delete_function(FunctionName=function_name)
            except lambda_client.exceptions.ResourceNotFoundException:
                pass

    def add_left_over_resources_from_stack(self, stack_name):
        resources = boto3.client("cloudformation").describe_stack_resources(StackName=stack_name).get("StackResources")
        for resource in resources:
            resource_type = resource.get("ResourceType")
            resource_physical_id = resource.get("PhysicalResourceId")
            if resource_type == "AWS::Lambda::Function":
                self.left_over_resources[ResourceType.LAMBDA_FUNCTION].append(resource_physical_id)
            elif resource_type == "AWS::IAM::Role":
                self.left_over_resources[ResourceType.IAM_ROLE].append(resource_physical_id)
            elif resource_type == "AWS::S3::Bucket":
                self.left_over_resources[ResourceType.S3_BUCKET].append(resource_physical_id)

    @staticmethod
    def get_deploy_command_list(
        s3_bucket=None,
        image_repository=None,
        image_repositories=None,
        stack_name=None,
        template=None,
        template_file=None,
        s3_prefix=None,
        capabilities=None,
        capabilities_list=None,
        force_upload=False,
        notification_arns=None,
        fail_on_empty_changeset=None,
        confirm_changeset=False,
        no_execute_changeset=False,
        parameter_overrides=None,
        role_arn=None,
        kms_key_id=None,
        tags=None,
        profile=None,
        region=None,
        guided=False,
        resolve_s3=False,
        config_file=None,
        signing_profiles=None,
        resolve_image_repos=False,
        disable_rollback=False,
    ):
        command_list = [get_sam_command(), "deploy"]

        if guided:
            command_list = command_list + ["--guided"]
        if s3_bucket:
            command_list = command_list + ["--s3-bucket", str(s3_bucket)]
        if image_repository:
            command_list = command_list + ["--image-repository", str(image_repository)]
        if image_repositories:
            command_list = command_list + ["--image-repositories", str(image_repositories)]
        if capabilities:
            command_list = command_list + ["--capabilities", str(capabilities)]
        elif capabilities_list:
            command_list.append("--capabilities")
            for capability in capabilities_list:
                command_list.append(str(capability))
        if parameter_overrides:
            command_list = command_list + ["--parameter-overrides", str(parameter_overrides)]
        if role_arn:
            command_list = command_list + ["--role-arn", str(role_arn)]
        if notification_arns:
            command_list = command_list + ["--notification-arns", str(notification_arns)]
        if stack_name:
            command_list = command_list + ["--stack-name", str(stack_name)]
        if template:
            command_list = command_list + ["--template", str(template)]
        if template_file:
            command_list = command_list + ["--template-file", str(template_file)]
        if s3_prefix:
            command_list = command_list + ["--s3-prefix", str(s3_prefix)]
        if kms_key_id:
            command_list = command_list + ["--kms-key-id", str(kms_key_id)]
        if no_execute_changeset:
            command_list = command_list + ["--no-execute-changeset"]
        if force_upload:
            command_list = command_list + ["--force-upload"]
        if fail_on_empty_changeset is None:
            pass
        elif fail_on_empty_changeset:
            command_list = command_list + ["--fail-on-empty-changeset"]
        else:
            command_list = command_list + ["--no-fail-on-empty-changeset"]
        if confirm_changeset:
            command_list = command_list + ["--confirm-changeset"]
        if tags:
            command_list = command_list + ["--tags", str(tags)]
        if region:
            command_list = command_list + ["--region", str(region)]
        if profile:
            command_list = command_list + ["--profile", str(profile)]
        if resolve_s3:
            command_list = command_list + ["--resolve-s3"]
        if config_file:
            command_list = command_list + ["--config-file", str(config_file)]
        if signing_profiles:
            command_list = command_list + ["--signing-profiles", str(signing_profiles)]
        if resolve_image_repos:
            command_list = command_list + ["--resolve-image-repos"]
        if disable_rollback:
            command_list = command_list + ["--disable-rollback"]

        return command_list

    @staticmethod
    def get_minimal_build_command_list(template_file=None, build_dir=None):
        command_list = [get_sam_command(), "build"]

        if template_file:
            command_list = command_list + ["--template-file", str(template_file)]
        if build_dir:
            command_list = command_list + ["--build-dir", str(build_dir)]

        return command_list
