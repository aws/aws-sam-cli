from mypy_boto3_cloudformation.client import CloudFormationClient
from mypy_boto3_s3.client import S3Client
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.deploy.deployer import Deployer
import boto3

from typing import List, Dict

from botocore.config import Config
from botocore.exceptions import ClientError, NoRegionError, NoCredentialsError
from samcli.commands.exceptions import CredentialsError, RegionError
from samcli.lib.bootstrap.companion_stack.companion_stack_builder import CompanionStackBuilder
from samcli.lib.bootstrap.companion_stack.data_types import CompanionStack, ECRRepo
from samcli.lib.package.artifact_exporter import mktempfile


class CompanionStackManager:
    _companion_stack: str
    _builder: CompanionStackBuilder
    _boto_config: Config
    _s3_bucket: str
    _s3_prefix: str
    _cfn_client: CloudFormationClient
    _s3_client: S3Client

    def __init__(self, stack_name, region, s3_bucket, s3_prefix):
        self._companion_stack = CompanionStack(stack_name)
        self._builder = CompanionStackBuilder(self._companion_stack)
        self._boto_config = Config(region_name=region if region else None)
        self._s3_bucket = s3_bucket
        self._s3_prefix = s3_prefix
        try:
            self._cfn_client = boto3.client("cloudformation", config=self._boto_config)
            self._ecr_client = boto3.client("ecr", config=self._boto_config)
            self._s3_client = boto3.client("s3", config=self._boto_config)
            self._account_id = boto3.client("sts").get_caller_identity().get("Account")
            self._region_name = self._cfn_client.meta.region_name
        except NoCredentialsError as ex:
            raise CredentialsError(
                "Error Setting Up Managed Stack Client: Unable to resolve credentials for the AWS SDK for Python client. "
                "Please see their documentation for options to pass in credentials: "
                "https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html"
            ) from ex
        except NoRegionError as ex:
            raise RegionError(
                "Error Setting Up Managed Stack Client: Unable to resolve a region. "
                "Please provide a region via the --region parameter or by the AWS_REGION environment variable."
            ) from ex

    def set_functions(self, function_logical_ids: List[str]) -> None:
        self._builder.clear_functions()
        for function_logical_id in function_logical_ids:
            self._builder.add_function(function_logical_id)

    def update_companion_stack(self) -> None:
        stack_name = self._companion_stack.stack_name
        template = self._builder.build()

        with mktempfile() as temporary_file:
            temporary_file.write(template)
            temporary_file.flush()

            s3_uploader = S3Uploader(
                self._s3_client, bucket_name=self._s3_bucket, prefix=self._s3_prefix, no_progressbar=True
            )
            # TemplateUrl property requires S3 URL to be in path-style format
            parts = S3Uploader.parse_s3_url(
                s3_uploader.upload_with_dedup(temporary_file.name, "template"), version_property="Version"
            )

        template_url = s3_uploader.to_path_style_s3_url(parts["Key"], parts.get("Version", None))
        waiter_config = {"Delay": 30, "MaxAttempts": 120}
        if self.does_companion_stack_exist():
            self._cfn_client.update_stack(
                StackName=stack_name, TemplateURL=template_url, Capabilities=["CAPABILITY_AUTO_EXPAND"]
            )
            waiter = self._cfn_client.get_waiter("stack_update_complete")
        else:
            self._cfn_client.create_stack(
                StackName=stack_name, TemplateURL=template_url, Capabilities=["CAPABILITY_AUTO_EXPAND"]
            )
            waiter = self._cfn_client.get_waiter("stack_create_complete")

        waiter.wait(StackName=stack_name, WaiterConfig=waiter_config)

    def list_deployed_repos(self) -> List[ECRRepo]:
        """
        Not using create_change_set as it is slow
        """
        if not self.does_companion_stack_exist():
            return None
        repos: List[ECRRepo] = list()
        stack = boto3.resource("cloudformation", config=self._boto_config).Stack(self._companion_stack.stack_name)
        resources = stack.resource_summaries.all()
        for resource in resources:
            if resource.resource_type == "AWS::ECR::Repository":
                repos.append(
                    ECRRepo(logical_id=resource.logical_resource_id, physical_id=resource.physical_resource_id)
                )
        return repos

    def get_unreferenced_repos(self) -> List[ECRRepo]:
        if not self.does_companion_stack_exist():
            return []
        deployed_repos: List[ECRRepo] = self.list_deployed_repos()
        current_mapping = self._builder.repo_mapping

        unreferenced_repos: List[ECRRepo] = list()
        for deployed_repo in deployed_repos:
            for _, current_repo in current_mapping.items():
                if current_repo.logical_id == deployed_repo.logical_id:
                    break
            else:
                unreferenced_repos.append(deployed_repo)
        return unreferenced_repos

    def delete_unreferenced_repos(self) -> None:
        repos = self.get_unreferenced_repos()
        for repo in repos:
            self._ecr_client.delete_repository(repositoryName=repo.physical_id, force=True)

    def does_companion_stack_exist(self) -> bool:
        try:
            self._cfn_client.describe_stacks(StackName=self._companion_stack.stack_name)
            return True
        except ClientError:
            return False

    def get_repository_mapping(self) -> Dict[str, str]:
        return dict((k, self.get_repo_uri(v)) for (k, v) in self._builder.repo_mapping.items())

    def get_repo_uri(self, repo: ECRRepo) -> str:
        return repo.get_repo_uri(self._account_id, self._region_name)
