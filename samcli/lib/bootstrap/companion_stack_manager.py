import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError, NoRegionError, NoCredentialsError
from samcli.commands.exceptions import UserException, CredentialsError, RegionError

from samcli.lib.bootstrap.ecr_bootstrap import CompanionStackBuilder


class CompanionStackManager:
    def __init__(self, stack_name, function_logical_ids, region):
        self._builder = CompanionStackBuilder(stack_name)
        self._companion_stack_name = self._builder.get_companion_stack_name()

        try:
            self._cfn_client = boto3.client("cloudformation", config=Config(region_name=region if region else None))
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
        pass

    def list_current_repos(self):
        repos = list()
        stack = boto3.resource("cloudformation", "us-west-2").Stack(self._companion_stack_name)
        resources = stack.resource_summaries.all()
        for resource in resources:
            if resource.resource_type == "AWS::ECR::Repository":
                repos.append(resource.physical_resource_id)
        return repos


    def get_unreferenced_repos(self):
        pass

    def does_companion_stack_exist(self):
        try:
            self._cfn_client.describe_stacks(StackName=self._companion_stack_name)
            return True
        except ClientError:
            return False


manager = CompanionStackManager("test-ecr-stack", ["FuncA", "FuncB"], "us-west-2")
manager.list_current_repos()