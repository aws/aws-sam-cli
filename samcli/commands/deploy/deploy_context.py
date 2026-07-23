"""
Deploy a SAM stack
"""

# Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import json
import logging
import os
from typing import Dict, List, Optional

import boto3
import botocore.exceptions
import click

from samcli.commands.deploy import exceptions as deploy_exceptions
from samcli.commands.deploy.auth_utils import auth_per_resource
from samcli.commands.deploy.utils import (
    hide_noecho_parameter_overrides,
    print_deploy_args,
    sanitize_parameter_overrides,
)
from samcli.lib.cfn_language_extensions.sam_integration import resolve_language_extensions_enabled
from samcli.lib.deploy.deployer import Deployer
from samcli.lib.deploy.utils import FailureMode
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.boto_utils import get_boto_config_with_user_agent
from samcli.yamlhelper import yaml_parse

LOG = logging.getLogger(__name__)

_SAM_ECR_POLICY_SID = "SAMCliLambdaECRAccess"

_LAMBDA_ECR_POLICY_STATEMENT = {
    "Sid": _SAM_ECR_POLICY_SID,
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:GetRepositoryPolicy",
    ],
}


class DeployContext:
    MSG_SHOWCASE_CHANGESET = "\nChangeset created successfully. {changeset_id}\n"

    MSG_EXECUTE_SUCCESS = "\nSuccessfully created/updated stack - {stack_name} in {region}\n"

    MSG_CONFIRM_CHANGESET = "Deploy this changeset?"
    MSG_CONFIRM_CHANGESET_HEADER = "\nPreviewing CloudFormation changeset before deployment"

    def __init__(
        self,
        template_file,
        stack_name,
        s3_bucket,
        image_repository,
        image_repositories,
        force_upload,
        no_progressbar,
        s3_prefix,
        kms_key_id,
        parameter_overrides,
        capabilities,
        no_execute_changeset,
        role_arn,
        notification_arns,
        fail_on_empty_changeset,
        tags,
        region,
        profile,
        confirm_changeset,
        signing_profiles,
        use_changeset,
        disable_rollback,
        poll_delay,
        on_failure,
        max_wait_duration,
        language_extensions: Optional[bool] = None,
        express: bool = False,
    ):
        self.template_file = template_file
        self.stack_name = stack_name
        self.s3_bucket = s3_bucket
        self.image_repository = image_repository
        self.image_repositories = image_repositories
        self.force_upload = force_upload
        self.no_progressbar = no_progressbar
        self.s3_prefix = s3_prefix
        self.kms_key_id = kms_key_id
        self.parameter_overrides = parameter_overrides
        # Override certain CloudFormation pseudo-parameters based on values provided by customer
        self.global_parameter_overrides: Optional[Dict] = None
        if region:
            self.global_parameter_overrides = {IntrinsicsSymbolTable.AWS_REGION: region}
        self.capabilities = capabilities
        self.no_execute_changeset = no_execute_changeset
        self.role_arn = role_arn
        self.notification_arns = notification_arns
        self.fail_on_empty_changeset = fail_on_empty_changeset
        self.tags = tags
        self.region = region
        self.profile = profile
        self.s3_uploader = None
        self.deployer: Optional[Deployer] = None
        self.confirm_changeset = confirm_changeset
        self.signing_profiles = signing_profiles
        self.use_changeset = use_changeset
        self.disable_rollback = disable_rollback
        self.poll_delay = poll_delay
        self.on_failure = FailureMode(on_failure) if on_failure else FailureMode.ROLLBACK
        self._max_template_size = 51200
        self.max_wait_duration = max_wait_duration
        self._language_extensions_enabled = resolve_language_extensions_enabled(language_extensions)
        self.express = express

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    @property
    def language_extensions_enabled(self) -> bool:
        return self._language_extensions_enabled

    def run(self):
        """
        Execute deployment based on the argument provided by customers and samconfig.toml.
        """

        # Parse parameters
        with open(self.template_file, "r") as handle:
            template_str = handle.read()

        template_dict = yaml_parse(template_str)

        if not isinstance(template_dict, dict):
            raise deploy_exceptions.DeployFailedError(
                stack_name=self.stack_name, msg="{} not in required format".format(self.template_file)
            )

        parameters = self.merge_parameters(template_dict, self.parameter_overrides)

        template_size = os.path.getsize(self.template_file)
        if template_size > self._max_template_size and not self.s3_bucket:
            raise deploy_exceptions.DeployBucketRequiredError()
        boto_config = get_boto_config_with_user_agent()
        cloudformation_client = boto3.client(
            "cloudformation", region_name=self.region if self.region else None, config=boto_config
        )

        s3_client = None
        if self.s3_bucket:
            s3_client = boto3.client("s3", region_name=self.region if self.region else None, config=boto_config)

            self.s3_uploader = S3Uploader(
                s3_client, self.s3_bucket, self.s3_prefix, self.kms_key_id, self.force_upload, self.no_progressbar
            )

        self.deployer = Deployer(cloudformation_client, client_sleep=self.poll_delay)

        if self.image_repositories or self.image_repository:
            ecr_client = boto3.client("ecr", region_name=self.region if self.region else None, config=boto_config)
            _ensure_ecr_lambda_pull_policy(
                ecr_client,
                self.image_repositories if isinstance(self.image_repositories, dict) else None,
                self.image_repository or None,
            )

        region = s3_client._client_config.region_name if s3_client else self.region  # pylint: disable=W0212
        display_parameter_overrides = hide_noecho_parameter_overrides(template_dict, self.parameter_overrides)
        print_deploy_args(
            self.stack_name,
            self.s3_bucket,
            self.image_repositories if isinstance(self.image_repositories, dict) else self.image_repository,
            region,
            self.capabilities,
            display_parameter_overrides,
            self.confirm_changeset,
            self.signing_profiles,
            self.use_changeset,
            self.disable_rollback,
        )
        return self.deploy(
            self.stack_name,
            template_str,
            parameters,
            self.capabilities,
            self.no_execute_changeset,
            self.role_arn,
            self.notification_arns,
            self.s3_uploader,
            [{"Key": key, "Value": value} for key, value in self.tags.items()] if self.tags else [],
            region,
            self.fail_on_empty_changeset,
            self.confirm_changeset,
            self.use_changeset,
            self.disable_rollback,
        )

    def deploy(
        self,
        stack_name: str,
        template_str: str,
        parameters: List[dict],
        capabilities: List[str],
        no_execute_changeset: bool,
        role_arn: str,
        notification_arns: List[str],
        s3_uploader: S3Uploader,
        tags: List[str],
        region: str,
        fail_on_empty_changeset: bool = True,
        confirm_changeset: bool = False,
        use_changeset: bool = True,
        disable_rollback: bool = False,
    ):
        """
        Deploy the stack to cloudformation.
        - if changeset needs confirmation, it will prompt for customers to confirm.
        - if no_execute_changeset is True, the changeset won't be executed.

        Parameters
        ----------
        stack_name : str
            name of the stack
        template_str : str
            the string content of the template
        parameters : List[Dict]
            List of parameters
        capabilities : List[str]
            List of capabilities
        no_execute_changeset : bool
            A bool indicating whether to execute changeset
        role_arn : str
            the Arn of the role to create changeset
        notification_arns : List[str]
            Arns for sending notifications
        s3_uploader : S3Uploader
            S3Uploader object to upload files to S3 buckets
        tags : List[str]
            List of tags passed to CloudFormation
        region : str
            AWS region to deploy the stack to
        fail_on_empty_changeset : bool
            Should fail when changeset is empty
        confirm_changeset : bool
            Should wait for customer's confirm before executing the changeset
        use_changeset : bool
            Involve creation of changesets, false when using sam sync
        disable_rollback : bool
            Preserves the state of previously provisioned resources when an operation fails
        """
        stacks, _ = SamLocalStackProvider.get_stacks(
            self.template_file,
            parameter_overrides=sanitize_parameter_overrides(self.parameter_overrides),
            global_parameter_overrides=self.global_parameter_overrides,
            language_extensions_enabled=self._language_extensions_enabled,
        )
        auth_required_per_resource = auth_per_resource(stacks)

        for resource, authorization_required in auth_required_per_resource:
            if not authorization_required:
                click.secho(f"{resource} has no authentication.", fg="yellow")

        assert self.deployer is not None
        if self.express:
            deployment_config = {"Mode": "EXPRESS", "DisableRollback": disable_rollback}
        else:
            deployment_config = None

        if use_changeset:
            try:
                result, changeset_type = self.deployer.create_and_wait_for_changeset(
                    stack_name=stack_name,
                    cfn_template=template_str,
                    parameter_values=parameters,
                    capabilities=capabilities,
                    role_arn=role_arn,
                    notification_arns=notification_arns,
                    s3_uploader=s3_uploader,
                    tags=tags,
                    deployment_config=deployment_config,
                )
                click.echo(self.MSG_SHOWCASE_CHANGESET.format(changeset_id=result["Id"]))

                if no_execute_changeset:
                    return

                if confirm_changeset:
                    click.secho(self.MSG_CONFIRM_CHANGESET_HEADER, fg="yellow")
                    click.secho("=" * len(self.MSG_CONFIRM_CHANGESET_HEADER), fg="yellow")
                    if not click.confirm(f"{self.MSG_CONFIRM_CHANGESET}", default=False):
                        return

                marker_time = self.deployer.get_last_event_time(stack_name, 0)
                self.deployer.execute_changeset(result["Id"], stack_name, disable_rollback, express=self.express)
                self.deployer.wait_for_execute(
                    stack_name, changeset_type, disable_rollback, self.on_failure, marker_time, self.max_wait_duration
                )
                click.echo(self.MSG_EXECUTE_SUCCESS.format(stack_name=stack_name, region=region))
                if self.express:
                    click.secho(
                        "\nDeployed with CloudFormation Express mode. "
                        "Resources may still be stabilizing in the background.",
                        fg="yellow",
                    )

            except deploy_exceptions.ChangeEmptyError as ex:
                if fail_on_empty_changeset:
                    raise
                click.echo(str(ex))
            except deploy_exceptions.DeployFailedError:
                # Failed to deploy, check for DELETE action otherwise skip
                if self.on_failure == FailureMode.DELETE:
                    self.deployer.rollback_delete_stack(stack_name)
                raise

        else:
            try:
                result = self.deployer.sync(
                    stack_name=stack_name,
                    cfn_template=template_str,
                    parameter_values=parameters,
                    capabilities=capabilities,
                    role_arn=role_arn,
                    notification_arns=notification_arns,
                    s3_uploader=s3_uploader,
                    tags=tags,  # type: ignore[arg-type]
                    on_failure=self.on_failure,
                    deployment_config=deployment_config,
                )
                LOG.debug(result)

            except deploy_exceptions.DeployFailedError as ex:
                LOG.error(str(ex))
                raise

    @staticmethod
    def merge_parameters(template_dict: Dict, parameter_overrides: Dict) -> List[Dict]:
        """
        CloudFormation CreateChangeset requires a value for every parameter
        from the template, either specifying a new value or use previous value.
        For convenience, this method will accept new parameter values and
        generates a dict of all parameters in a format that ChangeSet API
        will accept

        :param template_dict:
        :param parameter_overrides:
        :return:
        """
        parameter_values: List[Dict] = []

        if not isinstance(template_dict.get("Parameters", None), dict):
            return parameter_values

        for key, _ in template_dict["Parameters"].items():
            obj = {"ParameterKey": key}

            if key in parameter_overrides:
                obj["ParameterValue"] = parameter_overrides[key]
            else:
                obj["UsePreviousValue"] = True

            parameter_values.append(obj)

        return parameter_values


def _extract_ecr_repo_name(ecr_uri: str) -> str:
    """
    Extract the ECR repository name from a full ECR URI.

    Examples
    --------
    123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo:latest  ->  my-repo
    123456789012.dkr.ecr.us-east-1.amazonaws.com/org/my-repo:v1  ->  org/my-repo
    """
    parts = ecr_uri.split("/", 1)
    repo_with_tag = parts[1] if len(parts) > 1 else parts[0]
    return repo_with_tag.split(":")[0]


def _ensure_ecr_lambda_pull_policy(
    ecr_client,
    image_repositories: Optional[Dict[str, str]],
    image_repository: Optional[str],
) -> None:
    """
    Pre-set Lambda pull permissions on all ECR repositories referenced by
    --image-repositories / --image-repository before the CloudFormation
    changeset is created.

    This prevents a race condition where CloudFormation's concurrent Lambda
    resource creation calls SetRepositoryPolicy in parallel, overwriting each
    other and causing intermittent 403 access errors (GitHub issue #8190).
    """
    if not image_repositories and not image_repository:
        return

    uris = list((image_repositories or {}).values())
    if image_repository:
        uris.append(image_repository)

    unique_repo_names = {_extract_ecr_repo_name(uri) for uri in uris if uri}

    for repo_name in unique_repo_names:
        _upsert_ecr_lambda_policy(ecr_client, repo_name)


def _upsert_ecr_lambda_policy(ecr_client, repo_name: str) -> None:
    """
    Idempotently upsert a Lambda pull policy statement on a single ECR repo.

    Soft-fails on AccessDenied so users who have manually pre-configured
    policies or whose IAM principal lacks ecr:SetRepositoryPolicy are not blocked.
    """

    existing_statements = []
    try:
        response = ecr_client.get_repository_policy(repositoryName=repo_name)
        policy_doc = json.loads(response.get("policyText", "{}"))
        existing_statements = policy_doc.get("Statement", [])
    except ecr_client.exceptions.RepositoryPolicyNotFoundException:
        existing_statements = []
    except botocore.exceptions.ClientError as ex:
        error_code = ex.response.get("Error", {}).get("Code", "")
        if error_code in ("AccessDeniedException", "AuthorizationErrorException"):
            LOG.warning(
                "Could not read ECR policy for '%s' (access denied). "
                "Skipping — ensure ecr:GetRepositoryPolicy permission to prevent "
                "intermittent Lambda 403 errors during deployment.",
                repo_name,
            )
            return
        raise deploy_exceptions.ECRPolicySetError(repo_name=repo_name, msg=str(ex)) from ex

    filtered = [s for s in existing_statements if s.get("Sid") != _SAM_ECR_POLICY_SID]

    merged_policy = {
        "Version": "2012-10-17",
        "Statement": filtered + [_LAMBDA_ECR_POLICY_STATEMENT],
    }

    try:
        ecr_client.set_repository_policy(
            repositoryName=repo_name,
            policyText=json.dumps(merged_policy),
            force=False,
        )
        LOG.info("Pre-set Lambda pull policy on ECR repository '%s'", repo_name)
    except botocore.exceptions.ClientError as ex:
        error_code = ex.response.get("Error", {}).get("Code", "")
        if error_code in ("AccessDeniedException", "AuthorizationErrorException"):
            LOG.warning(
                "Could not set ECR policy for '%s' (access denied). "
                "Skipping — ensure ecr:SetRepositoryPolicy permission to prevent "
                "intermittent Lambda 403 errors during deployment.",
                repo_name,
            )
            return
        raise deploy_exceptions.ECRPolicySetError(repo_name=repo_name, msg=str(ex)) from ex
