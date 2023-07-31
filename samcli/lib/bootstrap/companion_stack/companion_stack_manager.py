"""
    Companion stack manager
"""
import logging
from typing import Dict, List, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, NoRegionError
from mypy_boto3_cloudformation.client import CloudFormationClient
from mypy_boto3_cloudformation.type_defs import WaiterConfigTypeDef
from mypy_boto3_s3.client import S3Client

from samcli.commands.exceptions import AWSServiceClientError, RegionError
from samcli.lib.bootstrap.companion_stack.companion_stack_builder import CompanionStackBuilder
from samcli.lib.bootstrap.companion_stack.data_types import CompanionStack, ECRRepo
from samcli.lib.package.artifact_exporter import mktempfile
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.packagetype import IMAGE
from samcli.lib.utils.s3 import parse_s3_url

LOG = logging.getLogger(__name__)


class CompanionStackManager:
    """
    Manager class for a companion stack
    Used to create/update the remote stack
    """

    _companion_stack: CompanionStack
    _builder: CompanionStackBuilder
    _boto_config: Config
    _update_stack_waiter_config: WaiterConfigTypeDef
    _delete_stack_waiter_config: WaiterConfigTypeDef
    _s3_bucket: str
    _s3_prefix: str
    _cfn_client: CloudFormationClient
    _s3_client: S3Client

    def __init__(self, stack_name, region, s3_bucket, s3_prefix):
        self._companion_stack = CompanionStack(stack_name)
        self._builder = CompanionStackBuilder(self._companion_stack)
        self._boto_config = Config(region_name=region if region else None)
        self._update_stack_waiter_config = {"Delay": 10, "MaxAttempts": 120}
        self._delete_stack_waiter_config = {"Delay": 10, "MaxAttempts": 120}
        self._s3_bucket = s3_bucket
        self._s3_prefix = s3_prefix
        try:
            self._cfn_client = boto3.client("cloudformation", config=self._boto_config)
            self._ecr_client = boto3.client("ecr", config=self._boto_config)
            self._s3_client = boto3.client("s3", config=self._boto_config)
            self._account_id = boto3.client("sts").get_caller_identity().get("Account")
            self._region_name = self._cfn_client.meta.region_name
        except NoCredentialsError as ex:
            raise AWSServiceClientError(
                "Error Setting Up Managed Stack Client: Unable to resolve "
                "credentials for the AWS SDK for Python client. "
                "Please see their documentation for options to pass in credentials: "
                "https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html"
            ) from ex
        except NoRegionError as ex:
            raise RegionError(
                "Error Setting Up Managed Stack Client: Unable to resolve a region. "
                "Please provide a region via the --region parameter or by the AWS_REGION environment variable."
            ) from ex

    def set_functions(
        self, function_logical_ids: List[str], image_repositories: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Sets functions that need to have ECR repos created

        Parameters
        ----------
        function_logical_ids: List[str]
            Function logical IDs that need to have ECR repos created
        image_repositories: Optional[Dict[str, str]]
            Optional image repository mapping. Functions with non-auto-ecr URIs
            will be ignored.
        """
        self._builder.clear_functions()
        if image_repositories is None:
            image_repositories = dict()
        for function_logical_id in function_logical_ids:
            if function_logical_id not in image_repositories or self.is_repo_uri(
                image_repositories.get(function_logical_id), function_logical_id
            ):
                self._builder.add_function(function_logical_id)

    def update_companion_stack(self) -> None:
        """
        Blocking call to create or update the companion stack based on current functions
        Companion stack template will be updated to the s3 bucket first before deployment
        """
        if not self._builder.repo_mapping:
            return

        stack_name = self._companion_stack.stack_name
        template = self._builder.build()

        with mktempfile() as temporary_file:
            temporary_file.write(template)
            temporary_file.flush()

            s3_uploader = S3Uploader(
                self._s3_client, bucket_name=self._s3_bucket, prefix=self._s3_prefix, no_progressbar=True
            )
            # TemplateUrl property requires S3 URL to be in path-style format
            parts = parse_s3_url(
                s3_uploader.upload_with_dedup(temporary_file.name, "template"), version_property="Version"
            )

        template_url = s3_uploader.to_path_style_s3_url(parts["Key"], parts.get("Version", None))

        exists = self.does_companion_stack_exist()
        if exists:
            self._cfn_client.update_stack(
                StackName=stack_name, TemplateURL=template_url, Capabilities=["CAPABILITY_AUTO_EXPAND"]
            )
            update_waiter = self._cfn_client.get_waiter("stack_update_complete")
            update_waiter.wait(StackName=stack_name, WaiterConfig=self._update_stack_waiter_config)
        else:
            self._cfn_client.create_stack(
                StackName=stack_name, TemplateURL=template_url, Capabilities=["CAPABILITY_AUTO_EXPAND"]
            )
            create_waiter = self._cfn_client.get_waiter("stack_create_complete")
            create_waiter.wait(StackName=stack_name, WaiterConfig=self._update_stack_waiter_config)

    def _delete_companion_stack(self) -> None:
        """
        Blocking call to delete the companion stack
        """
        stack_name = self._companion_stack.stack_name
        waiter = self._cfn_client.get_waiter("stack_delete_complete")
        self._cfn_client.delete_stack(StackName=stack_name)
        waiter.wait(StackName=stack_name, WaiterConfig=self._delete_stack_waiter_config)

    def list_deployed_repos(self) -> List[ECRRepo]:
        """
        List deployed ECR repos for this companion stack
        Not using create_change_set as it is slow.

        Returns
        -------
        List[ECRRepo]
            List of ECR repos deployed for this companion stack
            Returns empty list if companion stack does not exist
        """
        if not self.does_companion_stack_exist():
            return []
        repos: List[ECRRepo] = list()
        stack = boto3.resource("cloudformation", config=self._boto_config).Stack(self._companion_stack.stack_name)
        for resource in stack.resource_summaries.all():
            if resource.resource_type == "AWS::ECR::Repository":
                repos.append(
                    ECRRepo(logical_id=resource.logical_resource_id, physical_id=resource.physical_resource_id)
                )
        return repos

    def get_unreferenced_repos(self) -> List[ECRRepo]:
        """
        List deployed ECR repos that is not referenced by current list of functions

        Returns
        -------
        List[ECRRepo]
            List of deployed ECR repos that is not referenced by current list of functions
            Returns empty list if companion stack does not exist
        """
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
        """
        Blocking call to delete all deployed ECR repos that are unreferenced by a function
        If repo does not exist, this will simply skip it.
        """
        repos = self.get_unreferenced_repos()
        for repo in repos:
            try:
                self._ecr_client.delete_repository(repositoryName=repo.physical_id, force=True)
            except self._ecr_client.exceptions.RepositoryNotFoundException:
                LOG.debug("Image repo [%s] not found in companion stack. Skipping deletion.", repo.physical_id)

    def sync_repos(self) -> None:
        """
        Blocking call to sync companion stack with the following actions
        Creates the stack if it does not exist, and updates it if it does.
        Deletes unreferenced repos if they exist.
        Deletes companion stack if there isn't any repo left.
        """
        has_repo = bool(self.get_repository_mapping())
        if self.does_companion_stack_exist():
            self.delete_unreferenced_repos()
            if has_repo:
                self.update_companion_stack()
            else:
                self._delete_companion_stack()
        elif has_repo:
            self.update_companion_stack()

    def does_companion_stack_exist(self) -> bool:
        """
        Does companion stack exist

        Returns
        -------
        bool
            Returns True if companion stack exists
        """
        try:
            self._cfn_client.describe_stacks(StackName=self._companion_stack.stack_name)
            return True
        except ClientError as e:
            error_message = e.response.get("Error", {}).get("Message")
            if error_message == f"Stack with id {self._companion_stack.stack_name} does not exist":
                return False
            raise e

    def get_repository_mapping(self) -> Dict[str, str]:
        """
        Get current function to repo mapping

        Returns
        -------
        Dict[str, str]
            Dictionary with key as function logical ID and value as ECR repo URI.
        """
        return dict((k, self.get_repo_uri(v)) for (k, v) in self._builder.repo_mapping.items())

    def get_repo_uri(self, repo: ECRRepo) -> str:
        """
        Get repo URI for a ECR repo

        Parameters
        ----------
        repo: ECRRepo

        Returns
        -------
        str
            ECR repo URI based on account ID and region.
        """
        return repo.get_repo_uri(self._account_id, self._region_name)

    def is_repo_uri(self, repo_uri: Optional[str], function_logical_id: str) -> bool:
        """
        Check whether repo URI is a companion stack repo

        Parameters
        ----------
        repo_uri: str
            Repo URI to be checked.

        function_logical_id: str
            Function logical ID associated with the image repo.

        Returns
        -------
        bool
            Returns True if repo_uri is a companion stack repo.
        """
        return repo_uri == self.get_repo_uri(ECRRepo(self._companion_stack, function_logical_id))


def sync_ecr_stack(
    template_file: str, stack_name: str, region: str, s3_bucket: str, s3_prefix: str, image_repositories: Dict[str, str]
) -> Dict[str, str]:
    """Blocking call to sync local functions with ECR Companion Stack

    Parameters
    ----------
    template_file : str
        Template file path.
    stack_name : str
        Stack name
    region : str
        AWS region
    s3_bucket : str
        S3 bucket
    s3_prefix : str
        S3 prefix for the bucket
    image_repositories : Dict[str, str]
        Mapping between function logical ID and ECR URI

    Returns
    -------
    Dict[str, str]
        Updated mapping of image_repositories. Auto ECR URIs are added
        for Functions without a repo specified.
    """
    image_repositories = image_repositories.copy() if image_repositories else {}
    manager = CompanionStackManager(stack_name, region, s3_bucket, s3_prefix)

    stacks = SamLocalStackProvider.get_stacks(template_file)[0]
    function_provider = SamFunctionProvider(stacks, ignore_code_extraction_warnings=True)
    function_logical_ids = [
        function.full_path for function in function_provider.get_all() if function.packagetype == IMAGE
    ]
    manager.set_functions(function_logical_ids, image_repositories)
    image_repositories.update(manager.get_repository_mapping())
    manager.sync_repos()
    return image_repositories
