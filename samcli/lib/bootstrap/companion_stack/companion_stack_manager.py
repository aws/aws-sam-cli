import boto3

from typing import List, Dict

from botocore.config import Config
from botocore.exceptions import ClientError, NoRegionError, NoCredentialsError
from samcli.commands.exceptions import CredentialsError, RegionError
from samcli.lib.bootstrap.companion_stack.ecr_bootstrap import CompanionStackBuilder
from samcli.lib.bootstrap.companion_stack.data_types import CompanionStack, ECRRepo


class CompanionStackManager:
    def __init__(self, stack_name, function_logical_ids, region):
        self._companion_stack = CompanionStack(stack_name)
        self._builder = CompanionStackBuilder(self._companion_stack)
        self._boto_config = Config(region_name=region if region else None)
        try:
            self._cfn_client = boto3.client("cloudformation", config=self._boto_config)
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

        for function_logical_id in function_logical_ids:
            self._builder.add_function(function_logical_id)

    def update_companion_stack(self):
        self._cfn_client.update_stack(StackName=self._companion_stack.stack_name, TemplateBody=self._builder.build())

    def list_deployed_repos(self) -> List[ECRRepo]:
        """
        Not using create_change_set as it is slow
        """
        repos:List[ECRRepo] = list()
        stack = boto3.resource("cloudformation", config=self._boto_config).Stack(self._companion_stack.stack_name)
        resources = stack.resource_summaries.all()
        for resource in resources:
            if resource.resource_type == "AWS::ECR::Repository":
                repos.append(ECRRepo(logical_id=resource.logical_resource_id,physical_id=resource.physical_resource_id))
        return repos

    def get_unreferenced_repos(self) -> List[ECRRepo]:
        deployed_repos:List[ECRRepo] = self.list_deployed_repos()
        current_mapping = self._builder.repo_mapping

        unreferenced_repos:List[ECRRepo] = list()
        for deployed_repo in deployed_repos:
            found = False
            for _, current_repo in current_mapping.items():
                if current_repo.logical_id == deployed_repo.logical_id:
                    found = True
                    break
            if not found:
                unreferenced_repos.append(deployed_repo)
        return unreferenced_repos


    def does_companion_stack_exist(self):
        try:
            self._cfn_client.describe_stacks(StackName=self._companion_stack.stack_name)
            return True
        except ClientError:
            return False


manager = CompanionStackManager("test-ecr-stack", ["FuncA", "FuncB"], "us-west-2")
print(manager.get_unreferenced_repos())
