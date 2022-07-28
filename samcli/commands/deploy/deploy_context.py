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

import logging
import os
from typing import Dict, List, Optional

import boto3
import click

from samcli.commands.deploy import exceptions as deploy_exceptions
from samcli.commands.deploy.auth_utils import auth_per_resource
from samcli.commands.deploy.utils import (
    sanitize_parameter_overrides,
    print_deploy_args,
    hide_noecho_parameter_overrides,
)
from samcli.lib.deploy.deployer import Deployer
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.boto_utils import get_boto_config_with_user_agent
from samcli.yamlhelper import yaml_parse

LOG = logging.getLogger(__name__)


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
        self.deployer = None
        self.confirm_changeset = confirm_changeset
        self.signing_profiles = signing_profiles
        self.use_changeset = use_changeset
        self.disable_rollback = disable_rollback
        self.poll_delay = poll_delay

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

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
        if template_size > 51200 and not self.s3_bucket:
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
        stack_name,
        template_str,
        parameters,
        capabilities,
        no_execute_changeset,
        role_arn,
        notification_arns,
        s3_uploader,
        tags,
        region,
        fail_on_empty_changeset=True,
        confirm_changeset=False,
        use_changeset=True,
        disable_rollback=False,
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
        )
        auth_required_per_resource = auth_per_resource(stacks)

        for resource, authorization_required in auth_required_per_resource:
            if not authorization_required:
                click.secho(f"{resource} may not have authorization defined.", fg="yellow")

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
                )
                click.echo(self.MSG_SHOWCASE_CHANGESET.format(changeset_id=result["Id"]))

                if no_execute_changeset:
                    return

                if confirm_changeset:
                    click.secho(self.MSG_CONFIRM_CHANGESET_HEADER, fg="yellow")
                    click.secho("=" * len(self.MSG_CONFIRM_CHANGESET_HEADER), fg="yellow")
                    if not click.confirm(f"{self.MSG_CONFIRM_CHANGESET}", default=False):
                        return

                self.deployer.execute_changeset(result["Id"], stack_name, disable_rollback)
                self.deployer.wait_for_execute(stack_name, changeset_type, disable_rollback)
                click.echo(self.MSG_EXECUTE_SUCCESS.format(stack_name=stack_name, region=region))

            except deploy_exceptions.ChangeEmptyError as ex:
                if fail_on_empty_changeset:
                    raise
                click.echo(str(ex))

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
                    tags=tags,
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
